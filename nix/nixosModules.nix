# nix/nixosModules.nix — the NixOS module for sarthi-agent
#
# This module shares its options, its renderers for config.yaml, .env and
# documents, and its state setup with the Home Manager module
# (nix/homeManagerModules.nix). The shared code is in nix/moduleCommon.nix.
# This file holds only the parts that need root: the service user, a system
# state directory, the system PATH, and container mode.
#
# Two modes:
#   container.enable = false (default) → native systemd service
#   container.enable = true            → OCI container (persistent writable layer)
#
# Container mode: sarthi runs from /nix/store bind-mounted read-only into a
# plain Ubuntu container. The writable layer (apt/pip/npm installs) persists
# across restarts and agent updates. Only image/volume/options changes trigger
# container recreation. Environment variables are written to $SARTHI_HOME/.env
# and read by sarthi at startup — no container recreation needed for env changes.
#
# Tool resolution: the sarthi wrapper uses --suffix PATH for nix store tools,
# so apt/uv-installed versions take priority. The container entrypoint provisions
# extensible tools on first boot: nodejs/npm via apt, uv via curl, and a Python
# 3.11 venv (bootstrapped entirely by uv) at ~/.venv with pip seeded. Agents get
# writable tool prefixes for npm i -g, pip install, uv tool install, etc.
#
# Usage:
#   services.sarthi-agent = {
#     enable = true;
#     settings.model.default = "anthropic/claude-sonnet-4";
#     environmentFiles = [ config.sops.secrets."sarthi/env".path ];
#   };
#
{ inputs, ... }:
{
  flake.nixosModules.default =
    {
      config,
      lib,
      options,
      pkgs,
      ...
    }:

    let
      cfg = config.services.sarthi-agent;
      common = import ./moduleCommon.nix { inherit lib; };

      effectivePackage = common.effectivePackage cfg;
      sarthi-agent = inputs.self.packages.${pkgs.stdenv.hostPlatform.system}.default;

      sarthiHome = "${cfg.stateDir}/.sarthi";

      # In container mode, the agent uses the mount path in the container.
      effectiveWorkDir = if cfg.container.enable then containerWorkDir else cfg.workingDirectory;

      # config.yaml mode: group-writable (0660) when interactive users share this
      # SARTHI_HOME via addToSystemPackages, so they can save settings through the
      # CLI/TUI without hitting EACCES; otherwise group-read-only (0640). Secrets
      # (.env) stay 0640 regardless.
      configYamlMode = if cfg.addToSystemPackages then "0660" else "0640";

      containerName = "sarthi-agent";
      containerDataDir = "/data"; # stateDir mount point inside container
      containerHomeDir = "/home/sarthi";

      # ── Container mode helpers ──────────────────────────────────────────
      containerBin =
        if cfg.container.backend == "docker" then
          "${pkgs.docker}/bin/docker"
        else
          "${pkgs.podman}/bin/podman";

      # Runs as root inside the container on every start. Provisions the
      # sarthi user + sudo on first boot (writable layer persists), then
      # drops privileges. Supports arbitrary base images (Debian, Alpine, etc).
      containerEntrypoint = pkgs.writeShellScript "sarthi-container-entrypoint" ''
        set -eu

        SARTHI_UID="''${SARTHI_UID:?SARTHI_UID must be set}"
        SARTHI_GID="''${SARTHI_GID:?SARTHI_GID must be set}"

        # ── Group: ensure a group with GID=$SARTHI_GID exists ──
        # Check by GID (not name) to avoid collisions with pre-existing groups
        # (e.g. GID 100 = "users" on Ubuntu)
        EXISTING_GROUP=$(getent group "$SARTHI_GID" 2>/dev/null | cut -d: -f1 || true)
        if [ -n "$EXISTING_GROUP" ]; then
          GROUP_NAME="$EXISTING_GROUP"
        else
          GROUP_NAME="sarthi"
          if command -v groupadd >/dev/null 2>&1; then
            groupadd -g "$SARTHI_GID" "$GROUP_NAME"
          elif command -v addgroup >/dev/null 2>&1; then
            addgroup -g "$SARTHI_GID" "$GROUP_NAME" 2>/dev/null || true
          fi
        fi

        # ── User: ensure a user with UID=$SARTHI_UID exists ──
        PASSWD_ENTRY=$(getent passwd "$SARTHI_UID" 2>/dev/null || true)
        if [ -n "$PASSWD_ENTRY" ]; then
          TARGET_USER=$(echo "$PASSWD_ENTRY" | cut -d: -f1)
          TARGET_HOME=$(echo "$PASSWD_ENTRY" | cut -d: -f6)
        else
          TARGET_USER="sarthi"
          TARGET_HOME="/home/sarthi"
          if command -v useradd >/dev/null 2>&1; then
            useradd -u "$SARTHI_UID" -g "$SARTHI_GID" -m -d "$TARGET_HOME" -s /bin/bash "$TARGET_USER"
          elif command -v adduser >/dev/null 2>&1; then
            adduser -u "$SARTHI_UID" -D -h "$TARGET_HOME" -s /bin/sh -G "$GROUP_NAME" "$TARGET_USER" 2>/dev/null || true
          fi
        fi
        mkdir -p "$TARGET_HOME"
        chown "$SARTHI_UID:$SARTHI_GID" "$TARGET_HOME"
        chmod 0750 "$TARGET_HOME"

        # Ensure SARTHI_HOME is owned by the target user.
        # Use find instead of chown -R: chown strips the setgid bit (kernel
        # behavior), destroying the 2770 permissions the NixOS activation
        # script sets for group access by hostUsers.  Only touch files with
        # wrong ownership so correctly-owned dirs keep their permission bits.
        if [ -n "''${SARTHI_HOME:-}" ] && [ -d "$SARTHI_HOME" ]; then
          find "$SARTHI_HOME" \! -user "$SARTHI_UID" -exec chown "$SARTHI_UID:$SARTHI_GID" {} +
        fi

        # ── Provision apt packages (first boot only, cached in writable layer) ──
        # sudo: agent self-modification
        # nodejs/npm: writable node so npm i -g works (nix store copies are read-only)
        #   Node 22 via NodeSource — Ubuntu 24.04 ships Node 18 which is EOL.
        # curl: needed for uv installer + NodeSource setup
        if [ ! -f /var/lib/sarthi-tools-provisioned ] && command -v apt-get >/dev/null 2>&1; then
          echo "First boot: provisioning agent tools..."
          apt-get update -qq
          apt-get install -y -qq sudo curl ca-certificates gnupg
          mkdir -p /etc/apt/keyrings
          curl -fsSL https://deb.nodesource.com/gpgkey/nodesource-repo.gpg.key \
            | gpg --dearmor -o /etc/apt/keyrings/nodesource.gpg
          echo "deb [signed-by=/etc/apt/keyrings/nodesource.gpg] https://deb.nodesource.com/node_22.x nodistro main" \
            > /etc/apt/sources.list.d/nodesource.list
          apt-get update -qq
          apt-get install -y -qq nodejs
          touch /var/lib/sarthi-tools-provisioned
        fi

        if command -v sudo >/dev/null 2>&1 && [ ! -f /etc/sudoers.d/sarthi ]; then
          mkdir -p /etc/sudoers.d
          echo "$TARGET_USER ALL=(ALL) NOPASSWD:ALL" > /etc/sudoers.d/sarthi
          chmod 0440 /etc/sudoers.d/sarthi
        fi

        # uv (Python manager) — not in Ubuntu repos, retry-safe outside the sentinel
        if ! command -v uv >/dev/null 2>&1 && [ ! -x "$TARGET_HOME/.local/bin/uv" ] && command -v curl >/dev/null 2>&1; then
          su -s /bin/sh "$TARGET_USER" -c 'curl -LsSf https://astral.sh/uv/install.sh | sh' || true
        fi

        # Python 3.12 venv — gives the agent a writable Python with pip.
        # --seed includes pip/setuptools so bare `pip install` works.
        _UV_BIN="$TARGET_HOME/.local/bin/uv"
        if [ ! -d "$TARGET_HOME/.venv" ] && [ -x "$_UV_BIN" ]; then
          su -s /bin/sh "$TARGET_USER" -c "
            export PATH=\"\$HOME/.local/bin:\$PATH\"
            uv python install 3.12
            uv venv --python 3.12 --seed \"\$HOME/.venv\"
          " || true
        fi

        # Put the agent venv first on PATH so python/pip resolve to writable copies
        if [ -d "$TARGET_HOME/.venv/bin" ]; then
          export PATH="$TARGET_HOME/.venv/bin:$PATH"
        fi

        if command -v setpriv >/dev/null 2>&1; then
          exec setpriv --reuid="$SARTHI_UID" --regid="$SARTHI_GID" --init-groups "$@"
        elif command -v su >/dev/null 2>&1; then
          exec su -s /bin/sh "$TARGET_USER" -c 'exec "$0" "$@"' -- "$@"
        else
          echo "WARNING: no privilege-drop tool (setpriv/su), running as root" >&2
          exec "$@"
        fi
      '';

      # Identity hash — only recreate container when structural config changes.
      # Package and entrypoint use stable symlinks (current-package, current-entrypoint)
      # so they can update without recreation. Env vars go through $SARTHI_HOME/.env.
      containerIdentity = builtins.hashString "sha256" (
        builtins.toJSON {
          schema = 4; # bump when identity inputs change (4: Node 18→22 via NodeSource)
          image = cfg.container.image;
          extraVolumes = cfg.container.extraVolumes;
          extraOptions = cfg.container.extraOptions;
        }
      );

      identityFile = "${cfg.stateDir}/.container-identity";

      # The CLI on the host reads this file, in get_container_exec_info. The
      # file tells the CLI to run in the container and not on the host.
      containerModeFile = pkgs.writeText "sarthi-container-mode" ''
        # Written by the NixOS activation script. Do not edit manually.
        backend=${cfg.container.backend}
        container_name=${containerName}
        exec_user=${cfg.user}
        sarthi_bin=${containerDataDir}/current-package/bin/sarthi
      '';

      # Default: /var/lib/sarthi/workspace → /data/workspace.
      # Custom paths outside stateDir pass through unchanged (user must add extraVolumes).
      containerWorkDir =
        if lib.hasPrefix "${cfg.stateDir}/" cfg.workingDirectory then
          "${containerDataDir}/${lib.removePrefix "${cfg.stateDir}/" cfg.workingDirectory}"
        else
          cfg.workingDirectory;

      # The hardening and the environment that the gateway unit and the
      # backend unit share.
      commonServiceConfig = {
        User = cfg.user;
        Group = cfg.group;
        WorkingDirectory = cfg.workingDirectory;

        Restart = cfg.restart;
        RestartSec = cfg.restartSec;

        # Shared-state: files created by the service should be group-writable
        # so interactive users in the sarthi group can read/write them.
        UMask = "0007";

        # Hardening
        NoNewPrivileges = true;
        ProtectSystem = "strict";
        ProtectHome = false;
        ReadWritePaths = [
          cfg.stateDir
          cfg.workingDirectory
        ];
        PrivateTmp = true;
      };

      commonUnitEnvironment = {
        HOME = cfg.stateDir;
      }
      // common.processEnvironment { inherit sarthiHome; };

      unitPath = common.processPath { inherit pkgs cfg; };

    in
    {
      options.services.sarthi-agent =
        common.sharedOptions {
          defaultPackage = sarthi-agent;
          defaultPackageText = lib.literalExpression "sarthi-agent.packages.\${system}.default";
          defaultWorkingDirectory = "${cfg.stateDir}/workspace";
          defaultWorkingDirectoryText = lib.literalExpression ''"''${cfg.stateDir}/workspace"'';
        }
        // (
          with lib;
          {
            # ── Service identity ───────────────────────────────────────────
            user = mkOption {
              type = types.str;
              default = "sarthi";
              description = "System user running the gateway.";
            };

            group = mkOption {
              type = types.str;
              default = "sarthi";
              description = "System group running the gateway.";
            };

            createUser = mkOption {
              type = types.bool;
              default = true;
              description = "Create the user/group automatically.";
            };

            # ── Directories ────────────────────────────────────────────────
            stateDir = mkOption {
              type = types.str;
              default = "/var/lib/sarthi";
              description = "State directory. Contains .sarthi/ subdir (SARTHI_HOME).";
            };

            addToSystemPackages = mkOption {
              type = types.bool;
              default = false;
              description = ''
                Add the sarthi CLI to environment.systemPackages and export
                SARTHI_HOME system-wide (via environment.variables) so interactive
                shells share state with the gateway service.
              '';
            };

            # ── OCI Container (opt-in) ────────────────────────────────────
            container = {
              enable = mkEnableOption "OCI container mode (Ubuntu base, full self-modification support)";

              backend = mkOption {
                type = types.enum [
                  "docker"
                  "podman"
                ];
                default = "docker";
                description = "Container runtime.";
              };

              extraVolumes = mkOption {
                type = types.listOf types.str;
                default = [ ];
                description = "Extra volume mounts (host:container:mode format).";
                example = [ "/home/user/projects:/projects:rw" ];
              };

              extraOptions = mkOption {
                type = types.listOf types.str;
                default = [ ];
                description = "Extra arguments passed to docker/podman run.";
              };

              image = mkOption {
                type = types.str;
                default = "ubuntu:24.04";
                description = "OCI container image. The container pulls this at runtime via Docker/Podman.";
              };

              hostUsers = mkOption {
                type = types.listOf types.str;
                default = [ ];
                description = ''
                  Interactive users who get a ~/.sarthi symlink to the service
                  stateDir. These users are automatically added to the sarthi group.
                '';
                example = [ "sidbin" ];
              };
            };
          }
        );

      config = lib.mkIf cfg.enable (
        lib.mkMerge [

          # ── Merge MCP servers into settings ────────────────────────────────
          (lib.mkIf (cfg.mcpServers != { }) {
            services.sarthi-agent.settings.mcp_servers = common.mcpServersToConfig cfg.mcpServers;
          })

          # ── User / group ──────────────────────────────────────────────────
          (lib.mkIf cfg.createUser {
            users.groups.${cfg.group} = { };
            users.users.${cfg.user} = {
              isSystemUser = true;
              group = cfg.group;
              home = cfg.stateDir;
              createHome = true;
              shell = pkgs.bashInteractive;
            };
          })

          # ── Host CLI ──────────────────────────────────────────────────────
          # Add the sarthi CLI to system PATH and export SARTHI_HOME system-wide
          # so interactive shells share state (sessions, skills, cron) with the
          # gateway service instead of creating a separate ~/.sarthi/.
          (lib.mkIf cfg.addToSystemPackages {
            environment.systemPackages = [ effectivePackage ];
            environment.variables.SARTHI_HOME = sarthiHome;
          })

          # ── Host user group membership ─────────────────────────────────────
          (lib.mkIf (cfg.container.enable && cfg.container.hostUsers != [ ]) {
            users.users = lib.genAttrs cfg.container.hostUsers (_user: {
              extraGroups = [ cfg.group ];
            });
          })

          # ── Assertions ─────────────────────────────────────────────────────
          {
            assertions =
              common.pluginNameAssertions {
                inherit cfg;
                optionPath = "services.sarthi-agent";
              }
              ++ common.workspaceFilesAssertions {
                inherit cfg;
                opt = options.services.sarthi-agent.workingDirectory;
                optionPath = "services.sarthi-agent";
              }
              ++ common.backendBindAssertions {
                inherit cfg;
                optionPath = "services.sarthi-agent";
              }
              ++ [
                {
                  # Container mode runs one command in one container. A second
                  # process needs its own container and its own ports. This
                  # module does not do that.
                  assertion = !(cfg.container.enable && cfg.backend.mode != "none");
                  message = "services.sarthi-agent: backend.mode is not supported together with container.enable — the container runs the gateway only.";
                }
              ];
          }

          # ── Per-user profile for extraPackages ───────────────────────────
          # Wire extraPackages into the sarthi user's per-user profile so the
          # login-shell snapshot (which rebuilds PATH from NixOS profiles) sees
          # them.  The systemd service PATH also includes them for direct access.
          (lib.mkIf (cfg.extraPackages != [ ]) {
            # listOf options are merged by the NixOS module system — this appends to
            # any packages the operator assigned to this user externally (e.g. when
            # createUser = false and the user definition lives elsewhere in the config).
            users.users.${cfg.user}.packages = cfg.extraPackages;
          })

          # ── Warnings ──────────────────────────────────────────────────────
          (lib.mkIf
            (cfg.container.enable && !cfg.addToSystemPackages && cfg.container.hostUsers != [ ])
            {
              warnings = [
                ''
                  services.sarthi-agent: container.enable is true and container.hostUsers
                  is set, but addToSystemPackages is false. Without a host-installed sarthi
                  binary, container routing will not work for interactive users.
                  Set addToSystemPackages = true or ensure sarthi is on PATH.
                ''
              ];
            }
          )

          # ── Directories ───────────────────────────────────────────────────
          {
            systemd.tmpfiles.rules = [
              "d ${cfg.stateDir}                2770 ${cfg.user} ${cfg.group} - -"
              "d ${sarthiHome}                  2770 ${cfg.user} ${cfg.group} - -"
              "d ${cfg.stateDir}/home           0750 ${cfg.user} ${cfg.group} - -"
              "d ${cfg.workingDirectory}        2770 ${cfg.user} ${cfg.group} - -"
            ]
            ++ map (d: "d ${sarthiHome}/${d} 2770 ${cfg.user} ${cfg.group} - -") common.stateSubdirs;
          }

          # ── Activation: link config + auth + documents ────────────────────
          {
            system.activationScripts."sarthi-agent-setup" =
              lib.stringAfter
                (
                  [ "users" ] ++ lib.optional (config.system.activationScripts ? setupSecrets) "setupSecrets"
                )
                ''
                  # Ensure directories exist (activation runs before tmpfiles)
                  mkdir -p ${sarthiHome}
                  mkdir -p ${cfg.stateDir}/home
                  mkdir -p ${cfg.workingDirectory}
                  chown ${cfg.user}:${cfg.group} ${cfg.stateDir} ${sarthiHome} ${cfg.stateDir}/home ${cfg.workingDirectory}
                  chmod 2770 ${cfg.stateDir} ${sarthiHome} ${cfg.workingDirectory}
                  chmod 0750 ${cfg.stateDir}/home

                  # Create subdirs, set setgid + group-writable, migrate existing files.
                  # Nix-managed .env/.managed stay 0640/0644; config.yaml uses
                  # configYamlMode (0660 under addToSystemPackages, else 0640).
                  find ${sarthiHome} -maxdepth 1 \
                    \( -name "*.db" -o -name "*.db-wal" -o -name "*.db-shm" -o -name "SOUL.md" \) \
                    -exec chmod g+rw {} + 2>/dev/null || true
                  for _subdir in ${lib.concatStringsSep " " common.stateSubdirs}; do
                    mkdir -p "${sarthiHome}/$_subdir"
                    chown ${cfg.user}:${cfg.group} "${sarthiHome}/$_subdir"
                    chmod 2770 "${sarthiHome}/$_subdir"
                    find "${sarthiHome}/$_subdir" -type f \
                      -exec chmod g+rw {} + 2>/dev/null || true
                  done

                  ${common.mkStateScript {
                    inherit pkgs cfg sarthiHome;
                    workingDirectory = cfg.workingDirectory;
                    configWorkingDirectory = effectiveWorkDir;
                    owner = "${cfg.user}:${cfg.group}";
                    stateDirs = common.stateSubdirs;
                    modes = {
                      config = configYamlMode;
                      env = "0640";
                      managed = "0644";
                      auth = "0600";
                      document = "0640";
                    };
                  }}

                  chown -h ${cfg.user}:${cfg.group} ${sarthiHome}/plugins/nix-managed-* 2>/dev/null || true

                  # Container mode metadata — tells the host CLI to exec into the
                  # container instead of running locally. Removed when container mode
                  # is disabled so the host CLI falls back to native execution.
                  ${
                    if cfg.container.enable then
                      ''
                        install -o ${cfg.user} -g ${cfg.group} -m 0644 ${containerModeFile} ${sarthiHome}/.container-mode
                      ''
                    else
                      ''
                        rm -f ${sarthiHome}/.container-mode

                        # Remove symlink bridge for hostUsers
                        ${lib.concatStringsSep "\n" (
                          map (
                            user:
                            let
                              userHome = config.users.users.${user}.home;
                              symlinkPath = "${userHome}/.sarthi";
                            in
                            ''
                              if [ -L "${symlinkPath}" ] && [ "$(readlink "${symlinkPath}")" = "${sarthiHome}" ]; then
                                rm -f "${symlinkPath}"
                                echo "sarthi-agent: removed symlink ${symlinkPath}"
                              fi
                            ''
                          ) cfg.container.hostUsers
                        )}
                      ''
                  }

                  # ── Symlink bridge for interactive users ───────────────────────
                  # Create ~/.sarthi -> stateDir/.sarthi for each hostUser so the
                  # host CLI shares state with the container service.
                  # Only runs when container mode is enabled.
                  ${lib.optionalString cfg.container.enable (
                    lib.concatStringsSep "\n" (
                      map (
                        user:
                        let
                          userHome = config.users.users.${user}.home;
                          symlinkPath = "${userHome}/.sarthi";
                        in
                        ''
                          if [ -d "${symlinkPath}" ] && [ ! -L "${symlinkPath}" ]; then
                            # Real directory — back it up, then create symlink.
                            # (ln -sfn cannot atomically replace a directory.)
                            _backup="${symlinkPath}.bak.$(date +%s)"
                            echo "sarthi-agent: backing up existing ${symlinkPath} to $_backup"
                            mv "${symlinkPath}" "$_backup"
                          fi
                          # For everything else (existing symlink, doesn't exist, etc.)
                          # ln -sfn handles it: replaces symlinks, creates new ones.
                          ln -sfn "${sarthiHome}" "${symlinkPath}"
                          chown -h ${user}:${cfg.group} "${symlinkPath}"
                        ''
                      ) cfg.container.hostUsers
                    )
                  )}
                '';
          }

          # ══════════════════════════════════════════════════════════════════
          # MODE A: Native systemd service (default)
          # ══════════════════════════════════════════════════════════════════
          (lib.mkIf (!cfg.container.enable) {
            systemd.services.sarthi-agent = {
              description = "Sarthi Agent Gateway";
              wantedBy = [ "multi-user.target" ];
              after = [ "network-online.target" ];
              wants = [ "network-online.target" ];

              # cfg.environment and cfg.environmentFiles are written to
              # $SARTHI_HOME/.env by the activation script. load_sarthi_dotenv()
              # reads them at Python startup — no systemd EnvironmentFile needed.
              environment = commonUnitEnvironment;

              serviceConfig = commonServiceConfig // {
                ExecStart = lib.escapeShellArgs (common.gatewayArgv cfg);
              };

              path = unitPath;
            };
          })

          # ── The backend: sarthi serve or sarthi dashboard ─────────────────
          # This is a different process from the gateway. Both use one
          # SARTHI_HOME.
          (lib.mkIf (!cfg.container.enable && cfg.backend.mode != "none") {
            systemd.services.sarthi-backend = {
              description = common.backendDescription cfg;
              wantedBy = [ "multi-user.target" ];
              after = [ "network-online.target" ];
              wants = [ "network-online.target" ];

              environment = commonUnitEnvironment;

              serviceConfig = commonServiceConfig // {
                ExecStart = lib.escapeShellArgs (common.backendArgv { inherit pkgs cfg; });
              };

              path = unitPath;
            };
          })

          # ══════════════════════════════════════════════════════════════════
          # MODE B: OCI container (persistent writable layer)
          # ══════════════════════════════════════════════════════════════════
          (lib.mkIf cfg.container.enable {
            # Ensure the container runtime is available
            virtualisation.docker.enable = lib.mkDefault (cfg.container.backend == "docker");

            systemd.services.sarthi-agent = {
              description = "Sarthi Agent Gateway (container)";
              wantedBy = [ "multi-user.target" ];
              after = [
                "network-online.target"
              ]
              ++ lib.optional (cfg.container.backend == "docker") "docker.service";
              wants = [ "network-online.target" ];
              requires = lib.optional (cfg.container.backend == "docker") "docker.service";

              preStart = ''
                # Stable symlinks — container references these, not store paths directly
                ln -sfn ${effectivePackage} ${cfg.stateDir}/current-package
                ln -sfn ${containerEntrypoint} ${cfg.stateDir}/current-entrypoint

                # GC roots so nix-collect-garbage doesn't remove store paths in use
                ${pkgs.nix}/bin/nix-store --add-root ${cfg.stateDir}/.gc-root --indirect -r ${effectivePackage} 2>/dev/null || true
                ${pkgs.nix}/bin/nix-store --add-root ${cfg.stateDir}/.gc-root-entrypoint --indirect -r ${containerEntrypoint} 2>/dev/null || true

                # Check if container needs (re)creation
                NEED_CREATE=false
                if ! ${containerBin} inspect ${containerName} &>/dev/null; then
                  NEED_CREATE=true
                elif [ ! -f ${identityFile} ] || [ "$(cat ${identityFile})" != "${containerIdentity}" ]; then
                  echo "Container config changed, recreating..."
                  ${containerBin} rm -f ${containerName} || true
                  NEED_CREATE=true
                fi

                if [ "$NEED_CREATE" = "true" ]; then
                  # Resolve numeric UID/GID — passed to entrypoint for in-container user setup
                  SARTHI_UID=$(${pkgs.coreutils}/bin/id -u ${cfg.user})
                  SARTHI_GID=$(${pkgs.coreutils}/bin/id -g ${cfg.user})

                  echo "Creating container..."
                  ${containerBin} create \
                    --name ${containerName} \
                    --network=host \
                    --entrypoint ${containerDataDir}/current-entrypoint \
                    --volume /nix/store:/nix/store:ro \
                    --volume ${cfg.stateDir}:${containerDataDir} \
                    --volume ${cfg.stateDir}/home:${containerHomeDir} \
                    ${lib.concatStringsSep " " (map (v: "--volume ${v}") cfg.container.extraVolumes)} \
                    --env SARTHI_UID="$SARTHI_UID" \
                    --env SARTHI_GID="$SARTHI_GID" \
                    --env SARTHI_HOME=${containerDataDir}/.sarthi \
                    --env SARTHI_MANAGED=true \
                    --env HOME=${containerHomeDir} \
                    ${lib.concatStringsSep " " cfg.container.extraOptions} \
                    ${cfg.container.image} \
                    ${containerDataDir}/current-package/bin/sarthi gateway run --replace ${lib.concatStringsSep " " cfg.extraArgs}

                  echo "${containerIdentity}" > ${identityFile}
                fi
              '';

              script = ''
                exec ${containerBin} start -a ${containerName}
              '';

              preStop = ''
                ${containerBin} stop -t 10 ${containerName} || true
              '';

              serviceConfig = {
                Type = "simple";
                Restart = cfg.restart;
                RestartSec = cfg.restartSec;
                TimeoutStopSec = 30;
              };
            };
          })
        ]
      );
    };
}

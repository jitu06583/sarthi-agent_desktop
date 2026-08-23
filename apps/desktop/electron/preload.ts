import { contextBridge, ipcRenderer, webFrame, webUtils } from 'electron'

// Which translucency the OS can back. Asked synchronously because the renderer
// needs it before its first paint, and answered by main because deciding it
// needs `os.release()` — a sandboxed preload may only require electron, events,
// timers and url, so importing node:os here throws before contextBridge runs
// and takes the ENTIRE bridge down with it (window.sarthiDesktop undefined =>
// "Desktop IPC bridge is unavailable"). No reply means no glass, which degrades
// to an ordinary opaque window rather than a page thinned over nothing.
const translucencySupport = ipcRenderer.sendSync('sarthi:translucency:support')

contextBridge.exposeInMainWorld('sarthiDesktop', {
  glassSupported: translucencySupport?.glass === true,
  translucencySupported: translucencySupport?.translucency === true,
  getConnection: profile => ipcRenderer.invoke('sarthi:connection', profile),
  // Registry-scoped backend resolution: { connectionId, profile } → descriptor.
  getConnectionFor: payload => ipcRenderer.invoke('sarthi:connection:for', payload),
  getProfileRoutes: profiles => ipcRenderer.invoke('sarthi:plugin-profile-routes', profiles),
  revalidateConnection: () => ipcRenderer.invoke('sarthi:connection:revalidate'),
  touchBackend: profile => ipcRenderer.invoke('sarthi:backend:touch', profile),
  getGatewayWsUrl: profile => ipcRenderer.invoke('sarthi:gateway:ws-url', profile),
  // Registry-scoped fresh WS URL: { connectionId, profile } → result shape of
  // getGatewayWsUrl, minted against that connection's backend.
  getGatewayWsUrlFor: payload => ipcRenderer.invoke('sarthi:gateway:ws-url-for', payload),
  // Union agent roster across every registered connection.
  getAgentRoster: () => ipcRenderer.invoke('sarthi:agents:roster'),
  openSessionWindow: (sessionId, opts) => ipcRenderer.invoke('sarthi:window:openSession', sessionId, opts),
  openSessionInTerminal: (sessionId, opts) => ipcRenderer.invoke('sarthi:window:openInTerminal', sessionId, opts),
  openWindow: () => ipcRenderer.invoke('sarthi:window:openInstance'),
  claimAmbientCue: key => ipcRenderer.invoke('sarthi:ambient:claim', key),
  wakeIndicator: {
    getState: () => ipcRenderer.invoke('sarthi:wake-indicator:get'),
    setState: state => ipcRenderer.send('sarthi:wake-indicator:set', state),
    onState: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('sarthi:wake-indicator:state', listener)

      return () => ipcRenderer.removeListener('sarthi:wake-indicator:state', listener)
    }
  },
  petOverlay: {
    // Main renderer → main process: window lifecycle + drag. `request` is
    // `{ bounds, screen }`; resolves with the screen bounds it actually used.
    open: request => ipcRenderer.invoke('sarthi:pet-overlay:open', request),
    close: () => ipcRenderer.invoke('sarthi:pet-overlay:close'),
    setBounds: bounds => ipcRenderer.send('sarthi:pet-overlay:set-bounds', bounds),
    setIgnoreMouse: ignore => ipcRenderer.send('sarthi:pet-overlay:ignore-mouse', ignore),
    // Flip the overlay focusable (and focus it) while the composer needs keys.
    setFocusable: focusable => ipcRenderer.send('sarthi:pet-overlay:set-focusable', focusable),
    // Main renderer → overlay (forwarded by main): push the latest pet state.
    pushState: payload => ipcRenderer.send('sarthi:pet-overlay:state', payload),
    // Overlay → main renderer (forwarded by main): pop back in / composer submit.
    control: payload => ipcRenderer.send('sarthi:pet-overlay:control', payload),
    // Overlay subscribes to state pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sarthi:pet-overlay:state', listener)

      return () => ipcRenderer.removeListener('sarthi:pet-overlay:state', listener)
    },
    // Main renderer subscribes to overlay control messages.
    onControl: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sarthi:pet-overlay:control', listener)

      return () => ipcRenderer.removeListener('sarthi:pet-overlay:control', listener)
    }
  },
  // HUD mode: the chrome-free floating chat. A full app renderer (own gateway)
  // sized as a floating bar, so it mounts the real composer. Main owns the
  // window; `onChanged` keeps every window's toggle truthful.
  hud: {
    open: request => ipcRenderer.invoke('sarthi:hud:open', request),
    close: () => ipcRenderer.invoke('sarthi:hud:close'),
    setIgnoreMouse: ignore => ipcRenderer.send('sarthi:hud:ignore-mouse', ignore),
    moveBy: delta => ipcRenderer.send('sarthi:hud:move-by', delta),
    setBounds: bounds => ipcRenderer.send('sarthi:hud:set-bounds', bounds),
    // Whether the band covers the window below the bar. Main pairs it with the
    // user's translucency setting to decide the native frost (macOS vibrancy /
    // Windows 11 DWM backdrop) — see hudFrostFor.
    setFrost: showing => ipcRenderer.invoke('sarthi:hud:frost', showing),
    // The HUD tells main which session it is on; main hands that back to the
    // app window when the HUD closes, so the app can re-home onto it.
    setSession: sessionId => ipcRenderer.send('sarthi:hud:session', sessionId),
    onGoto: callback => {
      const listener = (_event, sessionId) => callback(sessionId)
      ipcRenderer.on('sarthi:hud:goto', listener)

      return () => ipcRenderer.removeListener('sarthi:hud:goto', listener)
    },
    onChanged: callback => {
      const listener = (_event, state) => callback(state)
      ipcRenderer.on('sarthi:hud:changed', listener)

      return () => ipcRenderer.removeListener('sarthi:hud:changed', listener)
    },
    // Linux only, and silent elsewhere: where the cursor is, in page
    // coordinates, or null when it has left the window. Stands in for the
    // mousemove that `setIgnoreMouseEvents(true, { forward: true })` delivers on
    // macOS and Windows but not here.
    onCursor: callback => {
      const listener = (_event, point) => callback(point)
      ipcRenderer.on('sarthi:hud:cursor', listener)

      return () => ipcRenderer.removeListener('sarthi:hud:cursor', listener)
    }
  },
  // Quick Entry: the global-hotkey mini composer window. Main owns the OS
  // shortcut + the persisted preference; the quick window only captures text
  // and hands it back, and the primary renderer submits it through the normal
  // prompt path.
  quickEntry: {
    getSettings: () => ipcRenderer.invoke('sarthi:quick-entry:settings:get'),
    setSettings: patch => ipcRenderer.invoke('sarthi:quick-entry:settings:set', patch),
    submit: payload => ipcRenderer.send('sarthi:quick-entry:submit', payload),
    dismiss: () => ipcRenderer.send('sarthi:quick-entry:dismiss'),
    // Primary renderer → main → quick window: gateway connection state + the
    // recent-session options the target picker offers. Main caches the latest
    // payload so a freshly spawned quick window starts from truth.
    pushState: payload => ipcRenderer.send('sarthi:quick-entry:state', payload),
    // Quick window subscribes to those pushes.
    onState: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sarthi:quick-entry:state', listener)

      return () => ipcRenderer.removeListener('sarthi:quick-entry:state', listener)
    },
    // Main → primary renderer: a submit captured by the quick window.
    onSubmit: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sarthi:quick-entry:submit', listener)

      return () => ipcRenderer.removeListener('sarthi:quick-entry:submit', listener)
    },
    // Main → quick window: you were just summoned (reset draft + refocus).
    onShown: callback => {
      const listener = () => callback()
      ipcRenderer.on('sarthi:quick-entry:shown', listener)

      return () => ipcRenderer.removeListener('sarthi:quick-entry:shown', listener)
    }
  },
  getBootProgress: () => ipcRenderer.invoke('sarthi:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('sarthi:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('sarthi:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('sarthi:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('sarthi:connection-config:test', payload),
  // v2 multi-connection registry: named agent sources (local / remote / cloud / ssh).
  connections: {
    list: () => ipcRenderer.invoke('sarthi:connections:list'),
    save: payload => ipcRenderer.invoke('sarthi:connections:save', payload),
    remove: id => ipcRenderer.invoke('sarthi:connections:remove', id),
    setPrimary: id => ipcRenderer.invoke('sarthi:connections:set-primary', id),
    setLaunchMode: mode => ipcRenderer.invoke('sarthi:connections:set-launch-mode', mode),
    setLastUsed: id => ipcRenderer.invoke('sarthi:connections:set-last-used', id),
    test: id => ipcRenderer.invoke('sarthi:connections:test', id),
    // Fan out `sarthi update` to every eligible registered connection.
    // Optional excludeIds skips rows the caller updates through another path.
    updateAll: options => ipcRenderer.invoke('sarthi:connections:update-all', options),
    // Registry lifecycle push (main → renderer): a connection was removed or
    // materially edited, so secondaries scoped to it must be disposed (and,
    // for edits, re-dialed at the new target).
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sarthi:connections:changed', listener)

      return () => ipcRenderer.removeListener('sarthi:connections:changed', listener)
    }
  },
  sshConfigHosts: () => ipcRenderer.invoke('sarthi:ssh-config:hosts'),
  sshResolveHost: host => ipcRenderer.invoke('sarthi:ssh-config:resolve', host),
  probeConnectionConfig: remoteUrl => ipcRenderer.invoke('sarthi:connection-config:probe', remoteUrl),
  oauthLoginConnectionConfig: remoteUrl => ipcRenderer.invoke('sarthi:connection-config:oauth-login', remoteUrl),
  oauthLogoutConnectionConfig: remoteUrl => ipcRenderer.invoke('sarthi:connection-config:oauth-logout', remoteUrl),
  // Sarthi Cloud: one portal login powers discovery + silent per-agent sign-in
  // (cloud-auto-discovery Phase 3).
  cloud: {
    status: () => ipcRenderer.invoke('sarthi:cloud:status'),
    login: () => ipcRenderer.invoke('sarthi:cloud:login'),
    logout: () => ipcRenderer.invoke('sarthi:cloud:logout'),
    discover: org => ipcRenderer.invoke('sarthi:cloud:discover', org),
    agentSignIn: dashboardUrl => ipcRenderer.invoke('sarthi:cloud:agent-sign-in', dashboardUrl)
  },
  profile: {
    get: () => ipcRenderer.invoke('sarthi:profile:get'),
    set: name => ipcRenderer.invoke('sarthi:profile:set', name)
  },
  api: request => ipcRenderer.invoke('sarthi:api', request),
  notify: payload => ipcRenderer.invoke('sarthi:notify', payload),
  requestMicrophoneAccess: () => ipcRenderer.invoke('sarthi:requestMicrophoneAccess'),
  readWindowBelow: () => ipcRenderer.invoke('sarthi:window:readBelow'),
  readFileDataUrl: filePath => ipcRenderer.invoke('sarthi:readFileDataUrl', filePath),
  readFileDataUrlForAttach: filePath => ipcRenderer.invoke('sarthi:readFileDataUrlForAttach', filePath),
  dataUrlReadMax: {
    get: () => ipcRenderer.invoke('sarthi:data-url-read-max:get'),
    set: maxMb => ipcRenderer.invoke('sarthi:data-url-read-max:set', maxMb)
  },
  readFileText: filePath => ipcRenderer.invoke('sarthi:readFileText', filePath),
  selectPaths: options => ipcRenderer.invoke('sarthi:selectPaths', options),
  selectSavePath: options => ipcRenderer.invoke('sarthi:selectSavePath', options),
  writeClipboard: text => ipcRenderer.invoke('sarthi:writeClipboard', text),
  readClipboard: () => ipcRenderer.invoke('sarthi:readClipboard'),
  saveGatewayFile: payload => ipcRenderer.invoke('sarthi:saveGatewayFile', payload),
  saveImageFromUrl: url => ipcRenderer.invoke('sarthi:saveImageFromUrl', url),
  contextMenuEdit: command => ipcRenderer.invoke('sarthi:context-menu:edit', command),
  contextMenuCopyImage: () => ipcRenderer.invoke('sarthi:context-menu:copy-image'),
  contextMenuSpellcheck: action => ipcRenderer.invoke('sarthi:context-menu:spellcheck', action),
  contextMenuGuestAddWord: payload => ipcRenderer.invoke('sarthi:context-menu:guest-add-word', payload),
  onContextMenuSpellcheck: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sarthi:context-menu-spellcheck', listener)

    return () => ipcRenderer.removeListener('sarthi:context-menu-spellcheck', listener)
  },
  saveImageBuffer: (data, ext) => ipcRenderer.invoke('sarthi:saveImageBuffer', { data, ext }),
  saveClipboardImage: () => ipcRenderer.invoke('sarthi:saveClipboardImage'),
  getPathForFile: file => {
    try {
      return webUtils.getPathForFile(file) || ''
    } catch {
      return ''
    }
  },
  normalizePreviewTarget: (target, baseDir) => ipcRenderer.invoke('sarthi:normalizePreviewTarget', target, baseDir),
  watchPreviewFile: url => ipcRenderer.invoke('sarthi:watchPreviewFile', url),
  watchDirectory: dir => ipcRenderer.invoke('sarthi:watchDirectory', dir),
  stopPreviewFileWatch: id => ipcRenderer.invoke('sarthi:stopPreviewFileWatch', id),
  setActiveWork: payload => ipcRenderer.send('sarthi:active-work', payload),
  setTitleBarTheme: payload => ipcRenderer.send('sarthi:titlebar-theme', payload),
  setNativeTheme: mode => ipcRenderer.send('sarthi:native-theme', mode),
  setTranslucency: payload => ipcRenderer.send('sarthi:translucency', payload),
  setKeepAwake: on => ipcRenderer.send('sarthi:keep-awake', on),
  setDisableF12: blocked => ipcRenderer.send('sarthi:devtools:disable-f12', blocked),
  setPreviewShortcutActive: active => ipcRenderer.send('sarthi:previewShortcutActive', Boolean(active)),
  openExternal: url => ipcRenderer.invoke('sarthi:openExternal', url),
  openPreviewInBrowser: url => ipcRenderer.invoke('sarthi:openPreviewInBrowser', url),
  reachPreviewUrl: url => ipcRenderer.invoke('sarthi:preview:reach', url),
  fetchLinkTitle: url => ipcRenderer.invoke('sarthi:fetchLinkTitle', url),
  resolveFavicon: url => ipcRenderer.invoke('sarthi:resolveFavicon', url),
  sanitizeWorkspaceCwd: cwd => ipcRenderer.invoke('sarthi:workspace:sanitize', cwd),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('sarthi:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('sarthi:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('sarthi:setting:defaultProjectDir:pick')
  },
  zoom: {
    // Current zoom of this window, as { level, percent }.
    get: () => ipcRenderer.invoke('sarthi:zoom:get'),
    // Synchronous zoom factor (1 = 100%). Coordinate math needs it in the
    // same tick as the event it converts, so no IPC round-trip here.
    factor: () => webFrame.getZoomFactor(),
    setPercent: percent => ipcRenderer.send('sarthi:zoom:set-percent', percent),
    // Fires on every zoom change, including the Ctrl/Cmd +/-/0 shortcuts,
    // so the settings UI can stay in sync with the keyboard.
    onChanged: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sarthi:zoom:changed', listener)

      return () => ipcRenderer.removeListener('sarthi:zoom:changed', listener)
    }
  },
  revealLogs: () => ipcRenderer.invoke('sarthi:logs:reveal'),
  getRecentLogs: () => ipcRenderer.invoke('sarthi:logs:recent'),
  // Fire-and-forget: persists a renderer error-boundary catch (with component
  // stack) to desktop.log so crashes survive the window (#79428).
  reportRendererError: report => ipcRenderer.send('sarthi:logs:renderer-error', report),
  readDir: dirPath => ipcRenderer.invoke('sarthi:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('sarthi:fs:gitRoot', startPath),
  revealPath: targetPath => ipcRenderer.invoke('sarthi:fs:reveal', targetPath),
  openDir: dirPath => ipcRenderer.invoke('sarthi:fs:openDir', dirPath),
  desktopPluginsRoot: () => ipcRenderer.invoke('sarthi:fs:desktopPluginsRoot'),
  logsRoot: () => ipcRenderer.invoke('sarthi:fs:logsRoot'),
  agentPluginsRoot: () => ipcRenderer.invoke('sarthi:fs:agentPluginsRoot'),
  renamePath: (targetPath, newName) => ipcRenderer.invoke('sarthi:fs:rename', targetPath, newName),
  writeTextFile: (filePath, content) => ipcRenderer.invoke('sarthi:fs:writeText', filePath, content),
  trashPath: targetPath => ipcRenderer.invoke('sarthi:fs:trash', targetPath),
  git: {
    worktreeList: repoPath => ipcRenderer.invoke('sarthi:git:worktreeList', repoPath),
    worktreeAdd: (repoPath, options) => ipcRenderer.invoke('sarthi:git:worktreeAdd', repoPath, options),
    worktreeRemove: (repoPath, worktreePath, options) =>
      ipcRenderer.invoke('sarthi:git:worktreeRemove', repoPath, worktreePath, options),
    branchSwitch: (repoPath, branch) => ipcRenderer.invoke('sarthi:git:branchSwitch', repoPath, branch),
    branchList: repoPath => ipcRenderer.invoke('sarthi:git:branchList', repoPath),
    baseBranchList: repoPath => ipcRenderer.invoke('sarthi:git:baseBranchList', repoPath),
    repoStatus: repoPath => ipcRenderer.invoke('sarthi:git:repoStatus', repoPath),
    fileDiff: (repoPath, filePath) => ipcRenderer.invoke('sarthi:git:fileDiff', repoPath, filePath),
    scanRepos: (roots, options) => ipcRenderer.invoke('sarthi:git:scanRepos', roots, options),
    review: {
      list: (repoPath, scope, baseRef) => ipcRenderer.invoke('sarthi:git:review:list', repoPath, scope, baseRef),
      diff: (repoPath, filePath, scope, baseRef, staged) =>
        ipcRenderer.invoke('sarthi:git:review:diff', repoPath, filePath, scope, baseRef, staged),
      stage: (repoPath, filePath) => ipcRenderer.invoke('sarthi:git:review:stage', repoPath, filePath),
      unstage: (repoPath, filePath) => ipcRenderer.invoke('sarthi:git:review:unstage', repoPath, filePath),
      revert: (repoPath, filePath) => ipcRenderer.invoke('sarthi:git:review:revert', repoPath, filePath),
      revParse: (repoPath, ref) => ipcRenderer.invoke('sarthi:git:review:revParse', repoPath, ref),
      commit: (repoPath, message, push) => ipcRenderer.invoke('sarthi:git:review:commit', repoPath, message, push),
      commitContext: repoPath => ipcRenderer.invoke('sarthi:git:review:commitContext', repoPath),
      push: repoPath => ipcRenderer.invoke('sarthi:git:review:push', repoPath),
      shipInfo: repoPath => ipcRenderer.invoke('sarthi:git:review:shipInfo', repoPath),
      prList: (repoPath, branches, numbers) =>
        ipcRenderer.invoke('sarthi:git:review:prList', repoPath, branches, numbers),
      fetchPrComment: (repoPath, url) => ipcRenderer.invoke('sarthi:git:review:fetchPrComment', repoPath, url),
      createPr: repoPath => ipcRenderer.invoke('sarthi:git:review:createPr', repoPath)
    }
  },
  terminal: {
    cwd: id => ipcRenderer.invoke('sarthi:terminal:cwd', id),
    dispose: id => ipcRenderer.invoke('sarthi:terminal:dispose', id),
    resize: (id, size) => ipcRenderer.invoke('sarthi:terminal:resize', id, size),
    start: options => ipcRenderer.invoke('sarthi:terminal:start', options),
    write: (id, data) => ipcRenderer.invoke('sarthi:terminal:write', id, data),
    onData: (id, callback) => {
      const channel = `sarthi:terminal:${id}:data`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    },
    onExit: (id, callback) => {
      const channel = `sarthi:terminal:${id}:exit`
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on(channel, listener)

      return () => ipcRenderer.removeListener(channel, listener)
    }
  },
  onClosePreviewRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('sarthi:close-preview-requested', listener)

    return () => ipcRenderer.removeListener('sarthi:close-preview-requested', listener)
  },
  onPreviewNav: callback => {
    const listener = (_event, command) => callback(command)
    ipcRenderer.on('sarthi:preview-nav', listener)

    return () => ipcRenderer.removeListener('sarthi:preview-nav', listener)
  },
  onOpenFolderRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('sarthi:open-folder-requested', listener)

    return () => ipcRenderer.removeListener('sarthi:open-folder-requested', listener)
  },
  onOpenUpdatesRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('sarthi:open-updates', listener)

    return () => ipcRenderer.removeListener('sarthi:open-updates', listener)
  },
  onDeepLink: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sarthi:deep-link', listener)

    return () => ipcRenderer.removeListener('sarthi:deep-link', listener)
  },
  signalDeepLinkReady: () => ipcRenderer.invoke('sarthi:deep-link-ready'),
  probePluginRepo: payload => ipcRenderer.invoke('sarthi:plugin:probe', payload),
  installDesktopPlugin: payload => ipcRenderer.invoke('sarthi:plugin:installDesktop', payload),
  onWindowStateChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sarthi:window-state-changed', listener)

    return () => ipcRenderer.removeListener('sarthi:window-state-changed', listener)
  },
  onFocusSession: callback => {
    const listener = (_event, sessionId) => callback(sessionId)
    ipcRenderer.on('sarthi:focus-session', listener)

    return () => ipcRenderer.removeListener('sarthi:focus-session', listener)
  },
  onNotificationAction: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sarthi:notification-action', listener)

    return () => ipcRenderer.removeListener('sarthi:notification-action', listener)
  },
  onNotificationActivate: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sarthi:notification-activate', listener)

    return () => ipcRenderer.removeListener('sarthi:notification-activate', listener)
  },
  onPreviewFileChanged: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sarthi:preview-file-changed', listener)

    return () => ipcRenderer.removeListener('sarthi:preview-file-changed', listener)
  },
  onBackendExit: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sarthi:backend-exit', listener)

    return () => ipcRenderer.removeListener('sarthi:backend-exit', listener)
  },
  // Soft gateway-mode apply finished tearing down the primary backend. Renderer
  // should wipe session lists + re-dial without a window reload.
  onConnectionApplied: callback => {
    const listener = () => callback()
    ipcRenderer.on('sarthi:connection:applied', listener)

    return () => ipcRenderer.removeListener('sarthi:connection:applied', listener)
  },
  onPowerResume: callback => {
    const listener = () => callback()
    ipcRenderer.on('sarthi:power-resume', listener)

    return () => ipcRenderer.removeListener('sarthi:power-resume', listener)
  },
  // AC ↔ battery transitions; renderers slow their backstop polls on battery.
  getOnBattery: () => ipcRenderer.invoke('sarthi:power-battery:get'),
  onBatteryChanged: callback => {
    const listener = (_event, onBattery) => callback(Boolean(onBattery))
    ipcRenderer.on('sarthi:power-battery', listener)

    return () => ipcRenderer.removeListener('sarthi:power-battery', listener)
  },
  onBootProgress: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sarthi:boot-progress', listener)

    return () => ipcRenderer.removeListener('sarthi:boot-progress', listener)
  },
  // First-launch bootstrap progress -- emitted by the install.ps1 stage
  // runner in main.ts (apps/desktop/electron/bootstrap-runner.ts).
  // Renderer's install overlay subscribes to live events and queries the
  // current snapshot via getBootstrapState() to recover after a devtools
  // reload mid-bootstrap.
  getBootstrapState: () => ipcRenderer.invoke('sarthi:bootstrap:get'),
  continueBootstrapLocal: () => ipcRenderer.invoke('sarthi:bootstrap:continue-local'),
  resetBootstrap: () => ipcRenderer.invoke('sarthi:bootstrap:reset'),
  repairBootstrap: () => ipcRenderer.invoke('sarthi:bootstrap:repair'),
  cancelBootstrap: () => ipcRenderer.invoke('sarthi:bootstrap:cancel'),
  onBootstrapEvent: callback => {
    const listener = (_event, payload) => callback(payload)
    ipcRenderer.on('sarthi:bootstrap:event', listener)

    return () => ipcRenderer.removeListener('sarthi:bootstrap:event', listener)
  },
  getVersion: () => ipcRenderer.invoke('sarthi:version'),
  getRemoteDisplayReason: () => ipcRenderer.invoke('sarthi:get-remote-display-reason'),
  uninstall: {
    summary: () => ipcRenderer.invoke('sarthi:uninstall:summary'),
    run: mode => ipcRenderer.invoke('sarthi:uninstall:run', { mode })
  },
  updates: {
    check: () => ipcRenderer.invoke('sarthi:updates:check'),
    apply: opts => ipcRenderer.invoke('sarthi:updates:apply', opts),
    getBranch: () => ipcRenderer.invoke('sarthi:updates:branch:get'),
    setBranch: name => ipcRenderer.invoke('sarthi:updates:branch:set', name),
    onProgress: callback => {
      const listener = (_event, payload) => callback(payload)
      ipcRenderer.on('sarthi:updates:progress', listener)

      return () => ipcRenderer.removeListener('sarthi:updates:progress', listener)
    }
  },
  themes: {
    fetchMarketplace: id => ipcRenderer.invoke('sarthi:vscode-theme:fetch', id),
    searchMarketplace: query => ipcRenderer.invoke('sarthi:vscode-theme:search', query)
  },
  // Find-in-page (Ctrl/Cmd+F): delegates to Electron's
  // webContents.findInPage on the IPC sender's window so a Cmd+F pressed
  // in a secondary session window searches THAT window, not the primary.
  // `onFoundInPage` returns the unsubscribe fn; the renderer wires it via
  // `initFindInPageListener` in store/find-in-page.ts and tears it down
  // when the FindBar unmounts.
  findInPage: (query, options) => ipcRenderer.invoke('sarthi:find-in-page', query, options),
  stopFindInPage: () => ipcRenderer.invoke('sarthi:stop-find-in-page'),
  onFoundInPage: callback => {
    const listener = (_event, result) => callback(result)
    ipcRenderer.on('sarthi:found-in-page', listener)

    return () => ipcRenderer.removeListener('sarthi:found-in-page', listener)
  },
  // Main-process `before-input-event` forwards Ctrl/Cmd+F here so renderer
  // can open the FindBar even when the GTK compositor has already grabbed
  // the chord at the windowing layer (#81727).
  onOpenFindBarRequested: callback => {
    const listener = () => callback()
    ipcRenderer.on('sarthi:open-find-bar', listener)

    return () => ipcRenderer.removeListener('sarthi:open-find-bar', listener)
  }
})

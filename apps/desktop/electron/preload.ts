import { contextBridge, ipcRenderer, webUtils } from 'electron'

contextBridge.exposeInMainWorld('sarthiDesktop', {
  getConnection: profile => ipcRenderer.invoke('sarthi:connection', profile),
  revalidateConnection: () => ipcRenderer.invoke('sarthi:connection:revalidate'),
  touchBackend: profile => ipcRenderer.invoke('sarthi:backend:touch', profile),
  getGatewayWsUrl: profile => ipcRenderer.invoke('sarthi:gateway:ws-url', profile),
  openSessionWindow: (sessionId, opts) => ipcRenderer.invoke('sarthi:window:openSession', sessionId, opts),
  openNewSessionWindow: () => ipcRenderer.invoke('sarthi:window:openNewSession'),
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
  getBootProgress: () => ipcRenderer.invoke('sarthi:boot-progress:get'),
  getConnectionConfig: profile => ipcRenderer.invoke('sarthi:connection-config:get', profile),
  saveConnectionConfig: payload => ipcRenderer.invoke('sarthi:connection-config:save', payload),
  applyConnectionConfig: payload => ipcRenderer.invoke('sarthi:connection-config:apply', payload),
  testConnectionConfig: payload => ipcRenderer.invoke('sarthi:connection-config:test', payload),
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
  readFileDataUrl: filePath => ipcRenderer.invoke('sarthi:readFileDataUrl', filePath),
  readFileText: filePath => ipcRenderer.invoke('sarthi:readFileText', filePath),
  selectPaths: options => ipcRenderer.invoke('sarthi:selectPaths', options),
  writeClipboard: text => ipcRenderer.invoke('sarthi:writeClipboard', text),
  saveImageFromUrl: url => ipcRenderer.invoke('sarthi:saveImageFromUrl', url),
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
  stopPreviewFileWatch: id => ipcRenderer.invoke('sarthi:stopPreviewFileWatch', id),
  setTitleBarTheme: payload => ipcRenderer.send('sarthi:titlebar-theme', payload),
  setNativeTheme: mode => ipcRenderer.send('sarthi:native-theme', mode),
  setTranslucency: payload => ipcRenderer.send('sarthi:translucency', payload),
  setPreviewShortcutActive: active => ipcRenderer.send('sarthi:previewShortcutActive', Boolean(active)),
  openExternal: url => ipcRenderer.invoke('sarthi:openExternal', url),
  openPreviewInBrowser: url => ipcRenderer.invoke('sarthi:openPreviewInBrowser', url),
  fetchLinkTitle: url => ipcRenderer.invoke('sarthi:fetchLinkTitle', url),
  sanitizeWorkspaceCwd: cwd => ipcRenderer.invoke('sarthi:workspace:sanitize', cwd),
  settings: {
    getDefaultProjectDir: () => ipcRenderer.invoke('sarthi:setting:defaultProjectDir:get'),
    setDefaultProjectDir: dir => ipcRenderer.invoke('sarthi:setting:defaultProjectDir:set', dir),
    pickDefaultProjectDir: () => ipcRenderer.invoke('sarthi:setting:defaultProjectDir:pick')
  },
  zoom: {
    // Current zoom of this window, as { level, percent }.
    get: () => ipcRenderer.invoke('sarthi:zoom:get'),
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
  readDir: dirPath => ipcRenderer.invoke('sarthi:fs:readDir', dirPath),
  gitRoot: startPath => ipcRenderer.invoke('sarthi:fs:gitRoot', startPath),
  revealPath: targetPath => ipcRenderer.invoke('sarthi:fs:reveal', targetPath),
  openDir: dirPath => ipcRenderer.invoke('sarthi:fs:openDir', dirPath),
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
  }
})

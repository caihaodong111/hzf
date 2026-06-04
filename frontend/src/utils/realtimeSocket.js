const DEFAULT_WS_PATH = '/ws/realtime/'

function buildRealtimeSocketUrl() {
  const protocol = window.location.protocol === 'https:' ? 'wss:' : 'ws:'
  return `${protocol}//${window.location.host}${DEFAULT_WS_PATH}`
}

export function createRealtimeSocket({
  onMessage,
  onOpen,
  onClose,
  onError,
  reconnectDelay = 3000
} = {}) {
  let socket = null
  let reconnectTimer = null
  let closedByClient = false

  const clearReconnectTimer = () => {
    if (reconnectTimer) {
      clearTimeout(reconnectTimer)
      reconnectTimer = null
    }
  }

  const scheduleReconnect = () => {
    if (closedByClient || reconnectTimer) return
    reconnectTimer = setTimeout(() => {
      reconnectTimer = null
      connect()
    }, reconnectDelay)
  }

  const connect = () => {
    if (closedByClient) return
    if (socket && [WebSocket.OPEN, WebSocket.CONNECTING].includes(socket.readyState)) {
      return
    }

    socket = new WebSocket(buildRealtimeSocketUrl())

    socket.onopen = (event) => {
      clearReconnectTimer()
      if (typeof onOpen === 'function') {
        onOpen(event)
      }
    }

    socket.onmessage = (event) => {
      if (typeof onMessage !== 'function') return
      try {
        const data = JSON.parse(event.data)
        onMessage(data)
      } catch (error) {
        onMessage(null, error)
      }
    }

    socket.onerror = (event) => {
      if (typeof onError === 'function') {
        onError(event)
      }
    }

    socket.onclose = (event) => {
      if (typeof onClose === 'function') {
        onClose(event)
      }
      scheduleReconnect()
    }
  }

  const close = () => {
    closedByClient = true
    clearReconnectTimer()
    if (socket) {
      socket.close()
      socket = null
    }
  }

  const isOpen = () => Boolean(socket && socket.readyState === WebSocket.OPEN)

  return {
    connect,
    close,
    isOpen
  }
}

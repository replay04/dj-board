// DJ Board Service Worker
const VAPID_PUBLIC_KEY = 'BLXShh_rR3xoqbyQoQ80MOTcqej_dIpwoMCHhuRZi3KIbaDMcPyckDgMbXOUP6abvBM1syWA2A6jKpzzf8PKDeo';

self.addEventListener('install', function(e) {
  self.skipWaiting();
});

self.addEventListener('activate', function(e) {
  e.waitUntil(clients.claim());
});

// Handle push notifications
self.addEventListener('push', function(e) {
  if (!e.data) return;
  
  var data = e.data.json();
  var options = {
    body: data.body || 'Nouveaux titres cette semaine !',
    icon: '/dj-board/icon.png',
    badge: '/dj-board/icon.png',
    vibrate: [200, 100, 200],
    data: { url: '/dj-board/' },
    actions: [
      { action: 'open', title: '🎵 Voir les nouveautés' }
    ]
  };
  
  e.waitUntil(
    self.registration.showNotification(data.title || '🎵 PADJ.fr Board', options)
  );
});

// Handle notification click
self.addEventListener('notificationclick', function(e) {
  e.notification.close();
  e.waitUntil(
    clients.openWindow(e.notification.data.url || '/dj-board/')
  );
});

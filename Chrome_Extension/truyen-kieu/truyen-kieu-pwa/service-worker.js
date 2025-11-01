const CACHE_NAME = 'boi-kieu-v1';
const urlsToCache = [
  './',
  './index.html',
  './app.js',
  './manifest.json',
  './icons/icon-192.png',
  './icons/icon-512.png'
];

// Default quotes for offline use
const defaultQuotes = [
  "Trăm năm trong cõi người ta, Chữ tài chữ mệnh khéo là ghét nhau.",
  "Trời xanh quen thói má hồng, Đánh phong cho bạc má hồng cho phai.",
  "Cỏ non xanh tận chân trời, Cành lê trắng điểm một vài bông hoa.",
  "Người đâu gặp gỡ làm chi, Trăm năm biết có duyên gì hay không?",
  "Bóng tà như thể như tin, Chẳng tea chẳng tất mà gần mà xa.",
  "Chim kia kíp núp cành dâu, Lại nhìn thước đất mà sầu cho ai.",
  "Sầu tuôn đứt nối châu sa, Cửa nào cũng đóng then mà cũng cài.",
  "Thuyền ai thấp thoáng cánh buồm, Làm chi những nhắc niềm thương nhớ.",
  "Rằng: Sao trong tiết thanh minh, Mà sao lạc mất dấu xinh người thương?",
  "Ngẫm hay muôn sự tại trời, Trời kia đã bắt làm người có thân."
];

// Install event
self.addEventListener('install', (event) => {
  event.waitUntil(
    caches.open(CACHE_NAME)
      .then((cache) => {
        console.log('Opened cache');
        return cache.addAll(urlsToCache);
      })
      .catch((error) => {
        console.error('Cache addAll error:', error);
      })
  );
  self.skipWaiting();
});

// Fetch event
self.addEventListener('fetch', (event) => {
  event.respondWith(
    caches.match(event.request)
      .then((response) => {
        // Return cached version or fetch new
        if (response) {
          return response;
        }

        return fetch(event.request).then((response) => {
          // Check if valid response
          if (!response || response.status !== 200 || response.type !== 'basic') {
            return response;
          }

          // Clone the response
          const responseToCache = response.clone();

          // Don't cache Google Docs requests
          if (!event.request.url.includes('docs.google.com')) {
            caches.open(CACHE_NAME)
              .then((cache) => {
                cache.put(event.request, responseToCache);
              });
          }

          return response;
        });
      })
      .catch(() => {
        // Offline fallback
        if (event.request.destination === 'document') {
          return caches.match('./index.html');
        }
      })
  );
});

// Activate event
self.addEventListener('activate', (event) => {
  const cacheWhitelist = [CACHE_NAME];

  event.waitUntil(
    caches.keys().then((cacheNames) => {
      return Promise.all(
        cacheNames.map((cacheName) => {
          if (cacheWhitelist.indexOf(cacheName) === -1) {
            return caches.delete(cacheName);
          }
        })
      );
    })
  );
  self.clients.claim();
});

// Background sync for notifications
self.addEventListener('sync', (event) => {
  if (event.tag === 'send-quote-notification') {
    event.waitUntil(sendQuoteNotification());
  }
});

// Handle notification clicks
self.addEventListener('notificationclick', (event) => {
  event.notification.close();
  
  event.waitUntil(
    clients.openWindow('./')
  );
});

// Push event for notifications
self.addEventListener('push', (event) => {
  const options = {
    body: event.data ? event.data.text() : getRandomQuote(),
    icon: './icons/icon-192.png',
    badge: './icons/icon-72.png',
    vibrate: [200, 100, 200],
    data: {
      dateOfArrival: Date.now(),
      primaryKey: 1
    },
    actions: [
      {
        action: 'explore',
        title: 'Xem thêm',
        icon: './icons/icon-72.png'
      },
      {
        action: 'close',
        title: 'Đóng',
        icon: './icons/icon-72.png'
      }
    ]
  };

  event.waitUntil(
    self.registration.showNotification('Bội Kiều - Lời tiên tri', options)
  );
});

// Periodic background sync
self.addEventListener('periodicsync', (event) => {
  if (event.tag === 'quote-sync') {
    event.waitUntil(sendQuoteNotification());
  }
});

// Helper function to get random quote
function getRandomQuote() {
  return defaultQuotes[Math.floor(Math.random() * defaultQuotes.length)];
}

// Send quote notification
async function sendQuoteNotification() {
  try {
    const clients = await self.clients.matchAll({ type: 'window' });
    
    // Get stored settings
    const cache = await caches.open(CACHE_NAME);
    let quote = getRandomQuote();
    
    // Try to get custom quotes if online
    if (navigator.onLine) {
      try {
        // This would be replaced with actual Google Doc fetch
        const response = await fetch('/api/quote');
        if (response.ok) {
          quote = await response.text();
        }
      } catch (error) {
        console.log('Using offline quotes');
      }
    }
    
    // Send notification
    await self.registration.showNotification('Bội Kiều - Lời tiên tri', {
      body: quote,
      icon: './icons/icon-192.png',
      badge: './icons/icon-72.png',
      vibrate: [200, 100, 200],
      tag: 'quote-notification',
      requireInteraction: false
    });
    
  } catch (error) {
    console.error('Error sending notification:', error);
  }
}

// Message handler for communication with app
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting();
  }
  
  if (event.data && event.data.type === 'SEND_NOTIFICATION') {
    sendQuoteNotification();
  }
});
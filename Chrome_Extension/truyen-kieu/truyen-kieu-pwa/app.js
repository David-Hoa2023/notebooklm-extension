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
  "Ngẫm hay muôn sự tại trời, Trời kia đã bắt làm người có thân.",
  "Đau đớn thay phận đàn bà, Lời rằng bạc mệnh cũng là lời chung.",
  "Nỗi niềm tưởng nỗi niềm nào, Suy ra mới biết rằng đau đớn nhiều.",
  "Bể sâu sóng cả đến đâu, Nghĩ mình mình lại thương đau của mình.",
  "Biết bao giờ bấc mới vừa, Nghĩ cơn lận đận mà chừa được nào.",
  "Nước trong như lọc, bụi trong như rây, Cây trong như vẽ, hoa trong như say."
];

let deferredPrompt;
let notificationInterval;
let currentQuote = "";

// Function to extract Google Doc ID from URL
function extractDocIdFromUrl(input) {
  if (!input) return null;
  
  // If it's already just an ID, return it
  if (!input.includes('/')) {
    return input;
  }
  
  // Try to extract ID from various Google Docs URL formats
  const patterns = [
    /\/document\/d\/([a-zA-Z0-9-_]+)/,  // Standard format
    /\/open\?id=([a-zA-Z0-9-_]+)/,       // Old format
    /docs\.google\.com\/.*\/d\/([a-zA-Z0-9-_]+)/, // Any docs format
  ];
  
  for (const pattern of patterns) {
    const match = input.match(pattern);
    if (match && match[1]) {
      return match[1];
    }
  }
  
  // If no pattern matches, return the original input
  return input.trim();
}

// Get quotes from Google Doc
async function getQuotesFromGoogleDoc(docId) {
  if (!docId) return defaultQuotes;
  
  const url = `https://docs.google.com/document/d/${docId}/export?format=txt`;
  
  try {
    const response = await fetch(url);
    
    if (!response.ok) {
      throw new Error('Failed to fetch document');
    }
    
    const text = await response.text();
    const quotes = text.split(/\n+/).filter(q => q.trim().length > 0);
    
    if (quotes.length === 0) {
      throw new Error('No quotes found in document');
    }
    
    return quotes;
  } catch (err) {
    console.error("Failed to fetch quotes:", err);
    return defaultQuotes;
  }
}

// Get random quote
async function getRandomQuote() {
  const docUrl = localStorage.getItem('docUrl');
  const docId = extractDocIdFromUrl(docUrl);
  const quotes = await getQuotesFromGoogleDoc(docId);
  const index = Math.floor(Math.random() * quotes.length);
  return quotes[index];
}

// Update status
function updateStatus(message) {
  const statusBar = document.getElementById('status');
  statusBar.style.opacity = '0';
  
  setTimeout(() => {
    statusBar.textContent = message;
    statusBar.style.opacity = '1';
  }, 200);
}

// Display fortune with animation
function displayFortune(fortune) {
  const fortuneText = document.getElementById('fortuneText');
  fortuneText.classList.remove('loading');
  currentQuote = fortune;
  
  // Mystical reveal animation
  let displayText = '';
  const chars = fortune.split('');
  let index = 0;
  
  const revealInterval = setInterval(() => {
    if (index < chars.length) {
      displayText += chars[index];
      fortuneText.textContent = displayText;
      index++;
    } else {
      clearInterval(revealInterval);
      
      // Add mystical glow effect
      fortuneText.style.color = '#ff00ff';
      fortuneText.style.textShadow = '0 0 10px rgba(255,0,255,0.8), 0 0 20px rgba(0,255,255,0.6)';
      setTimeout(() => {
        fortuneText.style.color = '#2a2a2a';
        fortuneText.style.textShadow = '0 1px 3px rgba(255,255,255,0.9)';
      }, 2000);
    }
  }, 30);
  
  updateStatus('🌸 LỜI TIÊN TRI ĐÃ HIỂN THỊ 🌸');
}

// Register service worker
if ('serviceWorker' in navigator) {
  window.addEventListener('load', () => {
    navigator.serviceWorker.register('./service-worker.js')
      .then((registration) => {
        console.log('ServiceWorker registration successful');
        
        // Check for updates periodically
        setInterval(() => {
          registration.update();
        }, 60000); // Check every minute
      })
      .catch((err) => {
        console.log('ServiceWorker registration failed: ', err);
      });
  });
}

// Handle install prompt
window.addEventListener('beforeinstallprompt', (e) => {
  e.preventDefault();
  deferredPrompt = e;
  
  // Show install banner
  const installBanner = document.getElementById('installBanner');
  installBanner.classList.add('show');
});

// Install button click
document.getElementById('installBtn').addEventListener('click', async () => {
  if (deferredPrompt) {
    deferredPrompt.prompt();
    const { outcome } = await deferredPrompt.userChoice;
    
    if (outcome === 'accepted') {
      console.log('User accepted the install prompt');
      updateStatus('✅ ỨNG DỤNG ĐÃ ĐƯỢC CÀI ĐẶT');
    }
    
    deferredPrompt = null;
    document.getElementById('installBanner').classList.remove('show');
  }
});

// Handle app installed
window.addEventListener('appinstalled', () => {
  console.log('PWA was installed');
  document.getElementById('installBanner').classList.remove('show');
});

// Save Google Doc URL
document.getElementById('saveDoc').addEventListener('click', () => {
  const docUrl = document.getElementById('docUrl').value.trim();
  
  if (docUrl) {
    localStorage.setItem('docUrl', docUrl);
    updateStatus('✅ ĐÃ LƯU NGUỒN THƠ');
    
    // Vibrate if supported
    if ('vibrate' in navigator) {
      navigator.vibrate(200);
    }
  } else {
    updateStatus('⚠️ VUI LÒNG NHẬP URL');
  }
});

// Bói Kiều button
document.getElementById('boiKieu').addEventListener('click', async () => {
  const fortuneText = document.getElementById('fortuneText');
  const button = document.getElementById('boiKieu');
  
  // Loading state
  fortuneText.textContent = '🔮 Đang tham khảo lời tiên tri...';
  fortuneText.classList.add('loading');
  button.disabled = true;
  
  // Vibrate if supported
  if ('vibrate' in navigator) {
    navigator.vibrate([100, 50, 100]);
  }
  
  try {
    const quote = await getRandomQuote();
    
    // Display with delay for effect
    setTimeout(() => {
      displayFortune(quote);
      button.disabled = false;
    }, 1500);
  } catch (error) {
    console.error('Error getting quote:', error);
    displayFortune(defaultQuotes[Math.floor(Math.random() * defaultQuotes.length)]);
    button.disabled = false;
  }
});

// Copy quote button
document.getElementById('copyQuote').addEventListener('click', () => {
  if (currentQuote) {
    if (navigator.clipboard) {
      navigator.clipboard.writeText(currentQuote).then(() => {
        updateStatus('✅ ĐÃ SAO CHÉP CÂU THƠ');
        
        // Vibrate if supported
        if ('vibrate' in navigator) {
          navigator.vibrate(100);
        }
      }).catch(() => {
        // Fallback for older browsers
        const textArea = document.createElement('textarea');
        textArea.value = currentQuote;
        document.body.appendChild(textArea);
        textArea.select();
        document.execCommand('copy');
        document.body.removeChild(textArea);
        updateStatus('✅ ĐÃ SAO CHÉP CÂU THƠ');
      });
    } else {
      // Fallback for older browsers
      const textArea = document.createElement('textarea');
      textArea.value = currentQuote;
      document.body.appendChild(textArea);
      textArea.select();
      document.execCommand('copy');
      document.body.removeChild(textArea);
      updateStatus('✅ ĐÃ SAO CHÉP CÂU THƠ');
    }
  }
});

// Notification toggle
document.getElementById('notificationToggle').addEventListener('change', async (e) => {
  const notificationSettings = document.getElementById('notificationSettings');
  
  if (e.target.checked) {
    // Request notification permission
    if ('Notification' in window) {
      const permission = await Notification.requestPermission();
      
      if (permission === 'granted') {
        notificationSettings.classList.add('show');
        updateStatus('🔔 ĐÃ BẬT THÔNG BÁO');
        startNotifications();
      } else {
        e.target.checked = false;
        updateStatus('⚠️ CẦN CHO PHÉP THÔNG BÁO');
      }
    } else {
      e.target.checked = false;
      updateStatus('⚠️ TRÌNH DUYỆT KHÔNG HỖ TRỢ');
    }
  } else {
    notificationSettings.classList.remove('show');
    stopNotifications();
    updateStatus('🔕 ĐÃ TẮT THÔNG BÁO');
  }
  
  localStorage.setItem('notificationsEnabled', e.target.checked);
});

// Interval selection
document.querySelectorAll('input[name="interval"]').forEach(radio => {
  radio.addEventListener('change', (e) => {
    const interval = parseInt(e.target.value);
    localStorage.setItem('notificationInterval', interval);
    
    if (document.getElementById('notificationToggle').checked) {
      stopNotifications();
      startNotifications();
      updateStatus(`⏰ THÔNG BÁO MỖI ${interval} PHÚT`);
    }
  });
});

// Start notifications
async function startNotifications() {
  const interval = parseInt(localStorage.getItem('notificationInterval') || '30');
  
  // Clear existing interval
  if (notificationInterval) {
    clearInterval(notificationInterval);
  }
  
  // Send immediate notification
  sendNotification();
  
  // Set up periodic notifications
  notificationInterval = setInterval(() => {
    sendNotification();
  }, interval * 60 * 1000);
  
  // Try to register periodic background sync if supported
  if ('serviceWorker' in navigator && 'periodicSync' in ServiceWorkerRegistration.prototype) {
    try {
      const registration = await navigator.serviceWorker.ready;
      await registration.periodicSync.register('quote-sync', {
        minInterval: interval * 60 * 1000
      });
    } catch (error) {
      console.log('Periodic sync not supported or permission denied');
    }
  }
}

// Stop notifications
function stopNotifications() {
  if (notificationInterval) {
    clearInterval(notificationInterval);
    notificationInterval = null;
  }
}

// Send notification
async function sendNotification() {
  if (Notification.permission === 'granted') {
    try {
      const quote = await getRandomQuote();
      
      if ('serviceWorker' in navigator) {
        const registration = await navigator.serviceWorker.ready;
        await registration.showNotification('Bội Kiều - Lời tiên tri', {
          body: quote,
          icon: './icons/icon-192.png',
          badge: './icons/icon-72.png',
          vibrate: [200, 100, 200],
          tag: 'quote-notification',
          requireInteraction: false,
          silent: false
        });
      } else {
        // Fallback to basic notification
        new Notification('Bội Kiều - Lời tiên tri', {
          body: quote,
          icon: './icons/icon-192.png'
        });
      }
    } catch (error) {
      console.error('Error sending notification:', error);
    }
  }
}

// Load saved settings on startup
window.addEventListener('DOMContentLoaded', () => {
  // Load saved doc URL
  const savedDocUrl = localStorage.getItem('docUrl');
  if (savedDocUrl) {
    document.getElementById('docUrl').value = savedDocUrl;
  }
  
  // Load notification settings
  const notificationsEnabled = localStorage.getItem('notificationsEnabled') === 'true';
  const notificationInterval = localStorage.getItem('notificationInterval') || '30';
  
  if (notificationsEnabled) {
    document.getElementById('notificationToggle').checked = true;
    document.getElementById('notificationSettings').classList.add('show');
    startNotifications();
  }
  
  // Set saved interval
  const intervalRadio = document.querySelector(`input[name="interval"][value="${notificationInterval}"]`);
  if (intervalRadio) {
    intervalRadio.checked = true;
  }
  
  // Add random visual effects on load
  setTimeout(() => {
    const bars = document.querySelectorAll('.bar');
    bars.forEach((bar, index) => {
      setTimeout(() => {
        bar.style.transform = 'scaleY(2)';
        setTimeout(() => {
          bar.style.transform = '';
        }, 200);
      }, index * 50);
    });
  }, 300);
  
  // Random status messages
  const randomMessages = [
    "◆ SẴN SÀNG XEM BÓI ◆",
    "🎵 CÂU THƠ ĐỒNG BỘ",
    "🌈 CHẾ ĐỘ TÍCH CỰC",
    "⚡ TRUYỀN CẢM HỨNG",
    "🎯 ĐỘNG LỰC SẴN SÀNG",
    "💫 TRUYỀN TẢI TRÍ TUỆ",
    "🔮 TIÊN TRI TRỰC TUYẾN",
    "🌸 TRÍ TUỆ KIỀU ĐANG CHỜ"
  ];
  
  // Change status randomly every 10 seconds
  setInterval(() => {
    const status = document.getElementById('status').textContent;
    if (status.includes('SẴN SÀNG') || 
        status.includes('ĐỒNG BỘ') || 
        status.includes('TÍCH CỰC') ||
        status.includes('TRỰC TUYẾN') ||
        status.includes('ĐANG CHỜ')) {
      const randomMsg = randomMessages[Math.floor(Math.random() * randomMessages.length)];
      updateStatus(randomMsg);
    }
  }, 10000);
});

// Handle online/offline status
window.addEventListener('online', () => {
  updateStatus('🌐 ĐÃ KẾT NỐI MẠNG');
});

window.addEventListener('offline', () => {
  updateStatus('📴 CHẾ ĐỘ OFFLINE');
});
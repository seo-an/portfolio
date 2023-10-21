module.exports = {
  apps : [{
    name: 'node-server',
    script: 'server.js',
    cwd: '/home/ubuntu/portfolio',
    post_update: ['npm install', 'pm2 restart node-server']
  }]
};

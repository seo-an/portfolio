module.exports = {
  apps : [{
    name: 'local-node-server',
    cwd: process.env.PM2_LOCAL_PATH,
    script: './server.js',
    source: process.env.PM2_LOCAL_PATH,
    post_update: ['npm install', 'pm2 restart local-node-server']
  },{
    name: 'staging-node-server',
    cwd: process.env.PM2_PROD_PATH,
    script: 'node server.js',
    source: process.env.PM2_PROD_PATH,
    post_update: ['npm install', 'pm2 restart staging-node-server'],
    out_file: '$HOME/logs/pm2/<pid>-staging-<app name>-out.log',
    error_file: '$HOME/logs/pm2/<pid>-staging-<app name>-error.log'
  },{
    name: 'prod-node-server',
    cwd: process.env.PM2_PROD_PATH,
    script: 'node server.js',
    source: process.env.PM2_PROD_PATH,
    post_update: ['npm install', 'pm2 restart prod-node-server'],
    out_file: '$HOME/logs/pm2/<pid>-prod-<app name>-out.log',
    error_file: '$HOME/logs/pm2/<pid>-prod-<app name>-error.log'
  }]
};

// module.exports = {
//   apps : [{
//     name: 'staging-node-server',
//     cwd: process.env.PM2_PROD_PATH,
//     script: './server.js',
//     source: process.env.PM2_PROD_PATH,
//     args: "--env staging",
//     post_update: ['npm install', 'pm2 restart staging-node-server']
//   },{
//     name: 'prod-node-server',
//     cwd: process.env.PM2_PROD_PATH,
//     script: './server.js',
//     source: process.env.PM2_PROD_PATH,
//     args: "--env production",
//     post_update: ['npm install', 'pm2 restart prod-node-server']
//   }]
// };

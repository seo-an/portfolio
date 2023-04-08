const mysql = require("mysql");
// require('dotenv').config();

// const localhostMysql = {
//   host: process.env.REACT_APP_MYSQL_CONF_LOCALHOST_HOST,
//   user: process.env.REACT_APP_MYSQL_CONF_LOCALHOST_USER,
//   password: process.env.REACT_APP_MYSQL_CONF_LOCALHOST_PASSWORD,
//   database: process.env.REACT_APP_MYSQL_CONF_LOCALHOST_DB,
//   port: process.env.REACT_APP_MYSQL_CONF_LOCALHOST_PORT
// };

// const localServerMysql = {
//   host: process.env.REACT_APP_MYSQL_CONF_LOCALSERVER_HOST,
//   user: process.env.REACT_APP_MYSQL_CONF_LOCALSERVER_USER,
//   password: process.env.REACT_APP_MYSQL_CONF_LOCALSERVER_PASSWORD,
//   database: process.env.REACT_APP_MYSQL_CONF_LOCALSERVER_DB,
//   port: process.env.REACT_APP_MYSQL_CONF_LOCALSERVER_PORT
// };

// const onDevServerMysql = {
//   host: process.env.REACT_APP_MYSQL_CONF_DEVSERVER_HOST,
//   user: process.env.REACT_APP_MYSQL_CONF_DEVSERVER_USER,
//   password: process.env.REACT_APP_MYSQL_CONF_DEVSERVER_PASSWORD,
//   database: process.env.REACT_APP_MYSQL_CONF_DEVSERVER_DB,
//   port: process.env.REACT_APP_MYSQL_CONF_DEVSERVER_PORT
// };

// const onProdServerMysql = {
//   host: process.env.REACT_APP_MYSQL_CONF_PRODSERVER_HOST,
//   user: process.env.REACT_APP_MYSQL_CONF_PRODSERVER_USER,
//   password: process.env.REACT_APP_MYSQL_CONF_PRODSERVER_PASSWORD,
//   database: process.env.REACT_APP_MYSQL_CONF_PRODSERVER_DB,
//   port: process.env.NODE_ENVREACT_APP_MYSQL_CONF_PRODSERVER_PORT
// };

module.exports = {
  init: function (conf) {
    // db와 서버 간 연결 객체 반환
    console.log('log', conf);
    const conn = new mysql.createConnection(conf);
    return conn;
  },
  connect: function (connention) {
    // db와 연결 (데이터 교환)
    connention.connect( (err) => {
      if (err) console.error('! CAN NOT CONNECT TO DATABASE ::', err);
      else {
        console.info(`SUCCESS! Database connected to :: MySQL`);
      };
    });
  }
};
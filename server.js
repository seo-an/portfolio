const express = require('express');
const cors = require('cors');
const path = require('path');
require('dotenv').config();
const app = express();
const dbConn = require("./database.js");
const { createPool } = require('mysql');

// Node.js server용 port
const PORT = 1991;

// Database connection
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

const onProdServerMysql = {
  host: process.env.MYSQL_CONF_PRODSERVER_HOST,
  user: process.env.MYSQL_CONF_PRODSERVER_USER,
  password: process.env.MYSQL_CONF_PRODSERVER_PASSWORD,
  database: process.env.MYSQL_CONF_PRODSERVER_DB,
  port: process.env.MYSQL_CONF_PRODSERVER_PORT,
};

// const connection = dbConn.init(onProdServerMysql);
// dbConn.connect(connection);
const connection = dbConn.pool(onProdServerMysql);

dbConn.connect(connection, `SELECT * FROM test`);



// json body parser
app.use(express.json());

// if (process.env.NODE_ENV === 'production') {
//   app.use('*', cors({
//     origin: "http://localhost:3000", // react server and external api
//     methods: ['GET', 'POST', 'PUT', 'DELETE'],
//     credentials: true,
//     optionsSuccessStatus: 200,
//   }));
// } else {
//   // 정적파일의 루트를 지정
//   app.use(express.static(path.join(__dirname, 'build')));

//   // 요청 url에 대한 응답페이지 지정
//   // '*' 으로 설정하면 react가 route의 전권을 가져갈 수 있음
//   app.get('*', (req, res) => {
//     res.sendFile(path.join(__dirname, 'build', 'index.html')); //res.sendFile(path.join(__dirname, 'build', 'index.html'));
//   });
// }

if (!process.env.NODE_ENV) {
  // 정적파일
  app.use(express.static(path.join(__dirname, 'build')));

} else if (process.env.NODE_ENV === 'production') {
  app.use(cors());

  // Define API route (internal API)
  app.get('/api/data/get', (req, res) => {
    const select = req.query.select;
    const from = req.query.from;
    const where = req.query.where;

    const READ_DATA = (where != '') ? `SELECT ${select} FROM ${from} WHERE ${where}` : `SELECT ${select} FROM ${from}`;

    connection.getConnection((err, conn) => {
      if(err) {
        console.error('CANNOT CONNECT TO DATABASE :: ', err);
        res.status(500).send('server error');
        return;
      }
    })
    connection.query(READ_DATA, (err, results, fields) => {
        if(!err) {
          res.header("content-type", 'application/json');
          res.send(results);
        }
        else res.send(err);
    });
  });


  app.post('/api/data/post', (req, res) => {
    const data = {...req.body[0]};
    console.log(data);
    const name = (data.name === undefined) ? null : data.name;
    const password = (data.simple_password === undefined) ? null : data.simple_password;
    const comment = (data.comment === undefined) ? null : data.comment;

    console.log(name, password, comment);

    // if ((!name) && (!password) && (!comment)) {
    //   const INSERT_DATA = `
    //     INSERT INTO ${process.env.DATABASE_TABLE_B} (
    //       name,
    //       simple_password,
    //       comment
    //     ) VALUE (
    //       '${name}',
    //       '${password}',
    //       '${comment}'
    //     );
    //   `;

    //   connection.query(INSERT_DATA, (err, results, fields) => {
    //     if(!err) {
    //       // res.header("content-type", 'application/json');
    //       res.sendStatus(200);
    //     }
    //     else res.send(err);
    //   });

    //   console.log(INSERT_DATA);
    // }
    res.send(data);

    
  });

  // React app
  app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'build', 'index.html'));
  });
  
  
}



// app.get('/api/data/dbcon', (req, res) => {
//   // Run your MySQL query
//   // connection.query(`SELECT * FROM test`, (err, results) => {
//   //   if (err) {
//   //     console.error('Error executing MySQL query:', err);
//   //     res.status(500).send('Error executing MySQL query');
//   //     return;
//   //   }

//   //   // Log the results
//   //   console.log('Results:', results);

//   //   // Send the results as a response
//   //   res.json(results);
//   // });

//   const { message } = req.body;
//   console.log('Received message:', message);

//   // JSON 데이터를 받은 후 필요한 처리를 수행

//   const response = { success: true, data: 'Message received' };
//   res.json(response);
//   // es.send(result);
// });








// 가장 마지막에
app.listen(PORT, () => {
    console.log(`Node.js server on :: Server listening on port ${PORT}`);
});
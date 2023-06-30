require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
// const { createPool } = require('mysql');

const app = express();
const mysqlConn = require("./database.js");

// Node.js express server용 port
const PORT = 1991;

// Database connection
// const localhostMysql = {
//   host: process.env.MYSQL_CONF_LOCALHOST_HOST,
//   user: process.env.MYSQL_CONF_LOCALHOST_USER,
//   password: process.env.MYSQL_CONF_LOCALHOST_PASSWORD,
//   database: process.env.MYSQL_CONF_LOCALHOST_DB,
//   port: process.env.MYSQL_CONF_LOCALHOST_PORT
// };

// const localServerMysql = {
//   host: process.env.MYSQL_CONF_LOCALSERVER_HOST,
//   user: process.env.MYSQL_CONF_LOCALSERVER_USER,
//   password: process.env.MYSQL_CONF_LOCALSERVER_PASSWORD,
//   database: process.env.MYSQL_CONF_LOCALSERVER_DB,
//   port: process.env.MYSQL_CONF_LOCALSERVER_PORT
// };

// const onDevServerMysql = {
//   host: process.env.MYSQL_CONF_DEVSERVER_HOST,
//   user: process.env.MYSQL_CONF_DEVSERVER_USER,
//   password: process.env.MYSQL_CONF_DEVSERVER_PASSWORD,
//   database: process.env.MYSQL_CONF_DEVSERVER_DB,
//   port: process.env.MYSQL_CONF_DEVSERVER_PORT
// };

const onProdServerMysql = {
  host: process.env.MYSQL_CONF_PRODSERVER_HOST,
  user: process.env.MYSQL_CONF_PRODSERVER_USER,
  password: process.env.MYSQL_CONF_PRODSERVER_PASSWORD,
  database: process.env.MYSQL_CONF_PRODSERVER_DB,
  port: process.env.MYSQL_CONF_PRODSERVER_PORT,
};

// const connection = mysqlConn.init(onProdServerMysql);
// mysqlConn.connect(connection);
const connection = mysqlConn.pool(onProdServerMysql);





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
  // get from database
  app.get('/api/data/get', (req, res) => {
    const select = req.query.select;
    const from = req.query.from;
    const where = req.query.where;

    const READ_DATA = (where !== '') ? `SELECT ${select} FROM ${from} WHERE ${where}` : `SELECT ${select} FROM ${from}`;

    mysqlConn.getConnect(res, connection, READ_DATA);

    // connection.getConnection((err, conn) => {
    //   if(err) {
    //     console.error('CANNOT CONNECT TO DATABASE :: ', err);
    //     res.status(500).send('server error');
    //     return;
    //   }
    // })
    // connection.query(READ_DATA, (err, results, fields) => {
    //     if(!err) {
    //       res.header("content-type", 'application/json');
    //       res.send(results);
    //     }
    //     else res.send(err);
    // });
  });


  // post to database
  app.post('/api/data/post', (req, res) => {
    console.log('in node (/api/data/post) : ', JSON.stringify(req.body[0]));
    const data = {...req.body[0]};

    const name = (data.name === undefined) ? null : ((data.name === '') ? null : data.name);
    const password = (data.simple_password === undefined) ? null : ((data.simple_password === '') ? null : data.simple_password);
    const comment = (data.comment === undefined) ? null : ((data.comment === '') ? null : data.comment);

    if ((name === null) || (password === null) || (comment === null)) {
      // handle error
      res.status(422).send('Unprocessable Entity: 올바른 값을 입력해주세요');
      return;
    }

    const prefix = String(new Date().getTime());
    // const uniqueId = String(`${name}${prefix}`);

    // const INSERT_DATA = `
    //   INSERT INTO ${process.env.DATABASE_TABLE_B} (
    //     name,
    //     simple_password,
    //     comment,
    //     uniqueId
    //   ) VALUE (
    //     '${name}',
    //     '${password}',
    //     '${comment}',
    //     CONCAT(AUTO_INCREMENT, '_${uniqueId}')
    //   );
    // `;
    

    const INSERT_DATA = `
      INSERT INTO ${process.env.DATABASE_TABLE_B} (uniqueId, name, simple_password, comment)
      SELECT
        CONCAT(MAX(id)+1,'_${name}','${prefix}') AS uniqueID,
        '${name}' AS name,
        '${password}' AS simple_password,
        '${comment}' AS comment
      FROM ${process.env.DATABASE_TABLE_B};
    `;


    mysqlConn.getConnect(res, connection, INSERT_DATA);
    //   connection.query(INSERT_DATA, (err, results, fields) => {
    //     if(!err) {
    //       // res.header("content-type", 'application/json');
    //       res.sendStatus(200);
    //     }
    //     else res.send(err);
    //   });

    //   console.log(INSERT_DATA);
    // }
    // res.send(data);
    
  });

  
  // React app
  app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'build', 'index.html'));
  });
  
}


// 가장 마지막에
app.listen(PORT, () => {
    console.log(`Node.js server on :: Server listening on port ${PORT}`);
});
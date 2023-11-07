require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const envSetting = require('./env.js');
// const { createPool } = require('mysql');

const app = express();
app.use(cors());
const mysqlConn = require("./database.js");

// Node.js express server용 port
const PORT = envSetting.NODE_SERVER_PORT || 1991;

// json body parser
app.use(express.json());


const dbConnection = mysqlConn.pool(envSetting.mysqlServerConf);

// Define API route (internal API)
// get from database
app.get('/api/guestbook/data', (req, res) => {
  const select = req.query.select;
  // const from = req.query.from; // 똑같잖아?
  const from = envSetting.API_INPUT_DATA_TO_THIS_TABLE;
  const where = req.query.where;

  const READ_DATA = (where !== '') ? `SELECT ${select} FROM ${from} WHERE ${where}` : `SELECT ${select} FROM ${from}`;

  console.log()
  mysqlConn.getConnect(res, dbConnection, READ_DATA);
});

// post to database
app.post('/api/guestbook/data', (req, res) => {
  console.log('in node (/api/guestbook/data) to post : ', JSON.stringify(req.body[0]));
  const data = {...req.body[0]};

  const name = (data.name === undefined) ? null : ((data.name === '') ? null : data.name);
  const password = (data.simple_password === undefined) ? null : ((data.simple_password === '') ? null : data.simple_password);
  const comment = (data.comment === undefined) ? null : ((data.comment === '') ? null : data.comment);
  const isPublic = true;
  const encoded = false;

  if ((name === null) || (password === null) || (comment === null)) {
    // handle error
    res.status(422).send('Unprocessable Entity: 올바른 값을 입력해주세요');
    return;
  }

  const prefix = String(new Date().getTime());

  // for real data
  const INSERT_DATA = `
    INSERT INTO ${envSetting.API_INPUT_DATA_TO_THIS_TABLE} (uniqueId, name, simple_password, comment, isPublic, isSecret)
    SELECT
      CONCAT(1+MAX(id),'_${name}','${prefix}') AS uniqueID,
      '${name}' AS name,
      '${password}' AS simple_password,
      '${comment}' AS comment,
      '${isPublic}' AS isPublic,
      '${encoded}' AS isSecret
    FROM ${envSetting.API_INPUT_DATA_TO_THIS_TABLE};
  `;

  mysqlConn.getConnect(res, dbConnection, INSERT_DATA);
});



app.use(express.static(path.join(__dirname, 'build', 'index.html')));
// '*' 으로 설정하면 react가 route의 전권을 가져갈 수 있음
// react가 route의 전권을 가져가게 되면 여기서 routing endpoint를 결정하는 것은 의미가 없음
app.get('*', (req, res) => {
  res.sendFile(path.join(__dirname, 'build', 'index.html'));
});


// 가장 마지막에
app.listen(PORT, () => {
    console.log(`Node.js server on :: Server listening on port ${PORT}`);
    console.log(`Now running environment :: ${process.env.NODE_ENV}`);

    // const http = require('http');
    // process.send('ready');
});
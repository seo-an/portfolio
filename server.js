require('dotenv').config();
const express = require('express');
const cors = require('cors');
const path = require('path');
const envSetting = require('./env.js');
const external = require('./https-request.js')
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
  console.log('Node.js server post to (/api/guestbook/data) : ', JSON.stringify(req.body[0]));
  const data = {...req.body[0]};

  const name = (data.name === undefined) ? null : ((data.name === '') ? null : data.name);
  const password = (data.simple_password === undefined) ? null : ((data.simple_password === '') ? null : data.simple_password);
  const comment = (data.comment === undefined) ? null : ((data.comment === '') ? null : data.comment);
  const isPublic = true;
  const encoded = false;

  if ((name === null) || (password === null) || (comment === null)) {
    // handle error
    res.status(422).send({
      message: 'Unprocessable Entity: 올바른 값을 입력해주세요',
      data: ''
    });
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


// const http = require('http');
// const https = require('https');
// const querystring = require('querystring');

app.post('/api/papago', async (req, res) => {
  // 내부 경로로 온 POST 요청을 처리
  const CLIENT_ID = process.env.NAVER_API_PAPAGO_CLIENT_ID_A;
  const CLIENT_SECRET = process.env.NAVER_API_PAPAGO_CLIENT_SECRET_A;

  const NAVER_API_HOSTNAME = 'openapi.naver.com';
  const PAPAGO_PATH = '/v1/papago/n2mt';

  // const ddata = querystring.stringify({
  //   source: req.body.source,
  //   target: req.body.target,
  //   text: req.body.text
  // });

  const data = {
    source: req.body.source,
    target: req.body.target,
    text: req.body.text
  };

  const externalOptions = {
    method: 'POST',
    hostname: NAVER_API_HOSTNAME,
    path: PAPAGO_PATH,
    headers: {
      'Content-Type': 'application/x-www-form-urlencoded; charset=UTF-8',
      'X-Naver-Client-Id': CLIENT_ID,
      'X-Naver-Client-Secret': CLIENT_SECRET,
    },
  };

  const responses = await external.externalRequestTo(externalOptions, data);

  res.status(200).json({ internal: 'GET External Response: SUCCESS', responses });

  // const externalReq = https.request(externalOptions, (externalRes) => {
  //   let data = '';

  //   externalRes.on('data', (str) => {
  //     data += str;
  //   });

  //   externalRes.on('end', () => {
  //     console.log('Papago API Response:', data);
  //     res.status(200).json({ internal: 'TRANSLATED DATA FROM PAPAGO', externalResponse: data });
  //   });
  // });

  // externalReq.on('error', (error) => {
  //   console.error('ERROR! External Request ::', error);
  //   res.status(500).json({ error: 'Internal Server Error' });
  // });

  // // 내부 요청에서 받은 데이터를 외부 서버로 전송
  // externalReq.write(ddata);
  // externalReq.end();
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
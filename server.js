const express = require('express');
const cors = require('cors');
const path = require('path');
require('dotenv').config();
const app = express();

// const PORT = 1991;
const PORT = process.env.PORT || 1991;

// DB conf
const localhostMysql = {
  host: process.env.REACT_APP_MYSQL_CONF_LOCALHOST_HOST,
  user: process.env.REACT_APP_MYSQL_CONF_LOCALHOST_USER,
  password: process.env.REACT_APP_MYSQL_CONF_LOCALHOST_PASSWORD,
  database: process.env.REACT_APP_MYSQL_CONF_LOCALHOST_DB,
  port: process.env.REACT_APP_MYSQL_CONF_LOCALHOST_PORT
};

const localServerMysql = {
  host: process.env.REACT_APP_MYSQL_CONF_LOCALSERVER_HOST,
  user: process.env.REACT_APP_MYSQL_CONF_LOCALSERVER_USER,
  password: process.env.REACT_APP_MYSQL_CONF_LOCALSERVER_PASSWORD,
  database: process.env.REACT_APP_MYSQL_CONF_LOCALSERVER_DB,
  port: process.env.REACT_APP_MYSQL_CONF_LOCALSERVER_PORT
};

const onDevServerMysql = {
  host: process.env.REACT_APP_MYSQL_CONF_DEVSERVER_HOST,
  user: process.env.REACT_APP_MYSQL_CONF_DEVSERVER_USER,
  password: process.env.REACT_APP_MYSQL_CONF_DEVSERVER_PASSWORD,
  database: process.env.REACT_APP_MYSQL_CONF_DEVSERVER_DB,
  port: process.env.REACT_APP_MYSQL_CONF_DEVSERVER_PORT
};

const onProdServerMysql = {
  host: process.env.REACT_APP_MYSQL_CONF_PRODSERVER_HOST,
  user: process.env.REACT_APP_MYSQL_CONF_PRODSERVER_USER,
  password: process.env.REACT_APP_MYSQL_CONF_PRODSERVER_PASSWORD,
  database: process.env.REACT_APP_MYSQL_CONF_PRODSERVER_DB,
  port: process.env.NODE_ENVREACT_APP_MYSQL_CONF_PRODSERVER_PORT
};

// Database Connection
const dbConfig = require("./database.js");
const connection = dbConfig.init(localhostMysql);
dbConfig.connect(connection);


// server-side code to allow Cross-Origin Resource Sharing for requests coming from a specific origin.
// 클라이언트가 다른 도메인의 리소스에 access할 수 있도록 response에 적절한 headers 설정해줌
// 반면 axios는 client-side library used to make HTTP requests from a web application.
// cors와 axios는 서로 다른 용도로 사용되며 서로에 대한 대안이 아님
// 서버 측 코드에서 app.use(cors()) 사용 -> 다른 도메인의 요청 허용
// 클라이언트 측 코드에서 axios 사용하여 API에 요청 (Open API의 경우)
app.use(cors());
// creating an express server and enabling cors so that we can make cross-origin requests to external APIs

// json body parser
app.use(express.json());

// RESTApi
// app.use('/api', (req, res) => {
//   console.log('????', req);
// });


if (process.env.NODE_ENV === 'production') {
  // 정적파일의 루트를 지정
  app.use(express.static('build'));

  // 요청 url에 대한 응답페이지 지정
  // '*' 으로 설정하면 react가 route의 전권을 가져갈 수 있음
  app.get('*', (req, res) => {
    res.sendFile(path.resolve(__dirname, 'build', 'index.html')); //res.sendFile(path.join(__dirname, 'build', 'index.html'));
  });
}

	// // RESTApi
  app.use('/api', (req, res) => {
    console.log('잘 몰라', req, res);
  });
	// app.use('/api', createProxyMiddleware({
  //   target: `http://192.168.0.27:3306`,
  //   changeOrigin: true,
  //   timeout: 60000,
  // })
// );

// 가장 마지막에
app.listen(PORT, () => {
    console.log(`Node.js server on :: Server listening on port ${PORT}`);
});


// REST API 메소드
// 첫번째 인자: End Point
// 두번째 인자: 콜백함수 - 이 함수는 두개의 인자를 받는다.
// '/user'에 get 요청이 오면 아래의 콜백함수가 실행이되는 것이다.
// app.get('/', function (req, res) {
//   // 첫번째 인자 req: 클라이언트에서 요청이올 때, ReqBody, ReqHeader, url 등등 그런 정보들이 모두 들어있다.
//   // 두번째 인자 res: 클라이언트에 응답할 때 필요한 모든 정보들이 들어있다. data 외에도 기본적으로 들어가야되는 네트워크 정보라던지 그런 것들이 모두 여기 들어있다.
// })
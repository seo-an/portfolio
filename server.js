const express = require('express');
const cors = require('cors');
const path = require('path');
require('dotenv').config();
const app = express();


// Node.js server용 port
const PORT = 1991;


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

  // React app
  app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'build', 'index.html'));
  });
  
  // backend API route (internal API)
  app.get('/api/data', (req, res) => {
    res.send('<h1>did you call me?</h1>');
  });
}


// 가장 마지막에
app.listen(PORT, () => {
    console.log(`Node.js server on :: Server listening on port ${PORT}`);
});
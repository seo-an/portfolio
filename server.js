const express = require('express');
const cors = require('cors');
const path = require('path');
require('dotenv').config();
const app = express();

// const PORT = 1991;
const PORT = process.env.PORT || 1991;

app.use(cors());


// json body parser
app.use(express.json());



if (process.env.NODE_ENV === 'production') {
  // 정적파일의 루트를 지정
  app.use(express.static('build'));

  // 요청 url에 대한 응답페이지 지정
  // '*' 으로 설정하면 react가 route의 전권을 가져갈 수 있음
  app.get('*', (req, res) => {
    res.sendFile(path.resolve(__dirname, 'build', 'index.html')); //res.sendFile(path.join(__dirname, 'build', 'index.html'));
  });
}

// 가장 마지막에
app.listen(PORT, () => {
    console.log(`Node.js server on :: Server listening on port ${PORT}`);
});
const mysql = require("mysql");

module.exports = {
  pool: function(conf) {
    // db와 서버 간 연결 객체 반환
    conf.connectionLimit = 13; // 활성화되는 db connection 개수
    const conn = new mysql.createPool(conf);
    return conn;
  },
  getConnect: async function(res, pool, queryString) {
    // console.log('연결', pool, '쿼리', queryString);
    const query = queryString;
    
    await pool.getConnection((err, connection) => {
      if (err) {
        console.error('! CAN NOT CONNECT TO DATABASE ::', err);
        res.status(500).send('Server error : to database');
        return;
      } 
      
      console.info(`SUCCESS! Database connected`);

      connection.query(query, (err, results) => {
        if(err) {
          res.status(400).send('Query execution error: ', err);
          connection.release();
          return;
        }

        res.header("content-type", 'application/json');
        res.status(200).send(results);

        connection.release();
      });
    });
  },
  postConnect: async function(res, pool, queryString) {
    // console.log('연결', pool, '쿼리', queryString);
    const query = queryString;
    
    await pool.getConnection((err, connection) => {
      if (err) {
        console.error('! CAN NOT CONNECT TO DATABASE ::', err);
        res.status(500).send('Server error : to database');
        return;
      } 

      console.info(`SUCCESS! Database connected`);

      connection.query(query, (err, results) => {
        if(err) {
          res.status(400).send(err);
          connection.release();
          return;
        }

        res.status(200).send('post completed');
        connection.release();

      });
    });
  }

};

// module.exports = {
//   init: function (conf) {
//     // db와 서버 간 연결 객체 반환
//     // console.log('log', conf);
//     const conn = new mysql.createConnection(conf);
//     return conn;
//   },
//   connect: function (connention) {
//     // db와 연결 (데이터 교환)
//     connention.connect( (err) => {
//       if (err) console.error('! CAN NOT CONNECT TO DATABASE ::', err);
//       else {
//         console.info(`SUCCESS! Database connected to :: MySQL`);
//       };
//     });
//   }
// };

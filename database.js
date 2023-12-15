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
        res.status(500).send({
          message: 'Server error : can not connect to database',
          data: err
        });
        // connection.release();
        return;
      } 
      
      console.info(`SUCCESS! Database connected`);

      connection.query(query, (err, results) => {
        
        if(err) {
          res.status(400).send({
            message: 'Query execution error',
            data: err
          });
          connection.release();
          return;
        }

        res.header("content-type", 'application/json');
        res.status(200).send({
          message: '200 OK',
          data: results
        });

        connection.release();
        return;
      });
    });
  },
  postConnect: async function(res, pool, queryString) {
    // console.log('연결', pool, '쿼리', queryString);
    const query = queryString;
    
    await pool.getConnection((err, connection) => {
      if (err) {
        console.error('! CAN NOT CONNECT TO DATABASE ::', err);
        res.status(500).send({
          message: 'Server error : can not connect to database',
          data: err
        });
        // connection.release();
        return;
      }

      console.info(`SUCCESS! Database connected`);

      connection.query(query, (err, results) => {
        if(err) {
          res.status(400).send({
            message: 'Query execution error',
            data: err
          });
          connection.release();
          return;
        }

        res.status(200).send({
          message: '200 OK',
          data: 'post completed'
        });

        connection.release();
        return;
      });
    });
  },
  deleteConnect: async function(res, pool, queryString) {
    // console.log('연결', pool, '쿼리', queryString);
    const query = queryString;

    try {
      await pool.getConnection((err, connection) => {
        console.info(`SUCCESS! Database connected`);
  
        connection.query(query, (err, results) => {
          if (err) {
            res.status(400).send({
                message: 'Query execution error',
                data: err
            });
  
            connection.release();
            return;
          }
  
          if (results.affectedRows === 0) {
            // No rows affected, which means the password didn't match
            res.status(401).send({
                message: 'Authentication error: invalid username or password',
                data: null
            });
  
            connection.release();
          }
  
          // res.header("content-type", 'application/json');
          res.status(200).send({
              message: '200 OK',
              data: results
          });
  
          connection.release();
          return;
        });
      });
    } catch (err) {
      console.error('! CAN NOT CONNECT TO DATABASE ::', err);
      res.status(500).send({
        message: 'Server error : can not connect to database',
        data: err
      });
      // connection.release();
      return;
    }
  },
  
};


// updateConnect: async function(res, pool, queryString) {
//   // console.log('연결', pool, '쿼리', queryString);
//   const query = queryString;
//   try {
//     await pool.getConnection((err, connection) => {
//       console.info(`SUCCESS! Database connected`);

//       connection.query(query, (err, results) => {
//         if (err) {
//           res.status(400).send({
//               message: 'Query execution error',
//               data: err
//           });

//           connection.release();
//           return;
//         }

//         if (results.affectedRows === 0) {
//           // No rows affected, which means the password didn't match
//           res.status(401).send({
//               message: 'Authentication error: invalid username or password',
//               data: null
//           });

//           connection.release();
//           return;
//         }

//         res.header("content-type", 'application/json');
//         res.status(200).send({
//             message: '200 OK',
//             data: results
//         });

//         connection.release();
//       });
//     });
//   } catch (err) {
//     console.error('! CAN NOT CONNECT TO DATABASE ::', err);
//     res.status(500).send({
//       message: 'Server error : can not connect to database',
//       data: err
//     });
//     // connection.release();
//     return;
//   }
// }


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

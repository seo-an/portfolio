const express = require('express');
const mysql = require("mysql");

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
          res.send('Query execution error: ', err);
          connection.release();
          return;
        }

        res.header("content-type", 'application/json');
        res.send(results);

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
          res.send(err);
          connection.release();
          return;
        }

        res.status(200).send('post completed');
        connection.release();

      });
    });
  }

};




// PoolConnection {
//   _events: [Object: null prototype] {
//     end: [Function: _removeFromPool],
//     error: [Function (anonymous)]
//   },
//   _eventsCount: 2,
//   _maxListeners: undefined,
//   config: ConnectionConfig {
//     host: 'ls-4bc51e1b7e7697cea034873d78dace84ee536579.cpfqei8aa9yx.ap-northeast-2.rds.amazonaws.com',
//     port: '3306',
//     localAddress: undefined,
//     socketPath: undefined,
//     user: 'carrot',
//     password: 'carrothater1991',
//     database: 'dbmaster',
//     connectTimeout: 10000,
//     insecureAuth: false,
//     supportBigNumbers: false,
//     bigNumberStrings: false,
//     dateStrings: false,
//     debug: undefined,
//     trace: true,
//     stringifyObjects: false,
//     timezone: 'local',
//     flags: '',
//     queryFormat: undefined,
//     pool: Pool {
//       _events: [Object: null prototype] {},
//       _eventsCount: 0,
//       _maxListeners: undefined,
//       config: [PoolConfig],
//       _acquiringConnections: [],
//       _allConnections: [Array],
//       _freeConnections: [],
//       _connectionQueue: [],
//       _closed: false,
//       [Symbol(kCapture)]: false
//     },
//     ssl: false,
//     localInfile: true,
//     multipleStatements: false,
//     typeCast: true,
//     maxPacketSize: 0,
//     charsetNumber: 33,
//     clientFlags: 455631,
//     protocol41: true
//   },
//   _socket: <ref *1> Socket {
//     connecting: false,
//     _hadError: false,
//     _parent: null,
//     _host: 'ls-4bc51e1b7e7697cea034873d78dace84ee536579.cpfqei8aa9yx.ap-northeast-2.rds.amazonaws.com',
//     _readableState: ReadableState {
//       objectMode: false,
//       highWaterMark: 16384,
//       buffer: BufferList { head: null, tail: null, length: 0 },
//       length: 0,
//       pipes: [],
//       flowing: true,
//       ended: false,
//       endEmitted: false,
//       reading: false,
//       constructed: true,
//       sync: false,
//       needReadable: true,
//       emittedReadable: false,
//       readableListening: false,
//       resumeScheduled: false,
//       errorEmitted: false,
//       emitClose: false,
//       autoDestroy: true,
//       destroyed: false,
//       errored: null,
//       closed: false,
//       closeEmitted: false,
//       defaultEncoding: 'utf8',
//       awaitDrainWriters: null,
//       multiAwaitDrain: false,
//       readingMore: false,
//       dataEmitted: true,
//       decoder: null,
//       encoding: null,
//       [Symbol(kPaused)]: false
//     },
//     _events: [Object: null prototype] {
//       end: [Array],
//       data: [Function (anonymous)],
//       error: [Function: bound ],
//       connect: [Function: bound ]
//     },
//     _eventsCount: 4,
//     _maxListeners: undefined,
//     _writableState: WritableState {
//       objectMode: false,
//       highWaterMark: 16384,
//       finalCalled: false,
//       needDrain: false,
//       ending: false,
//       ended: false,
//       finished: false,
//       destroyed: false,
//       decodeStrings: false,
//       defaultEncoding: 'utf8',
//       length: 0,
//       writing: false,
//       corked: 0,
//       sync: false,
//       bufferProcessing: false,
//       onwrite: [Function: bound onwrite],
//       writecb: null,
//       writelen: 0,
//       afterWriteTickInfo: null,
//       buffered: [],
//       bufferedIndex: 0,
//       allBuffers: true,
//       allNoop: true,
//       pendingcb: 0,
//       constructed: true,
//       prefinished: false,
//       errorEmitted: false,
//       emitClose: false,
//       autoDestroy: true,
//       errored: null,
//       closed: false,
//       closeEmitted: false,
//       [Symbol(kOnFinished)]: []
//     },
//     allowHalfOpen: false,
//     _sockname: null,
//     _pendingData: null,
//     _pendingEncoding: '',
//     server: null,
//     _server: null,
//     timeout: 0,
//     [Symbol(async_id_symbol)]: 11,
//     [Symbol(kHandle)]: TCP {
//       reading: true,
//       onconnection: null,
//       [Symbol(owner_symbol)]: [Circular *1]
//     },
//     [Symbol(lastWriteQueueSize)]: 0,
//     [Symbol(timeout)]: Timeout {
//       _idleTimeout: -1,
//       _idlePrev: null,
//       _idleNext: null,
//       _idleStart: 1907,
//       _onTimeout: null,
//       _timerArgs: undefined,
//       _repeat: null,
//       _destroyed: true,
//       [Symbol(refed)]: false,
//       [Symbol(kHasPrimitive)]: false,
//       [Symbol(asyncId)]: 15,
//       [Symbol(triggerId)]: 9
//     },
//     [Symbol(kBuffer)]: null,
//     [Symbol(kBufferCb)]: null,
//     [Symbol(kBufferGen)]: null,
//     [Symbol(kCapture)]: false,
//     [Symbol(kSetNoDelay)]: false,
//     [Symbol(kSetKeepAlive)]: false,
//     [Symbol(kSetKeepAliveInitialDelay)]: 0,
//     [Symbol(kBytesRead)]: 0,
//     [Symbol(kBytesWritten)]: 0
//   },
//   _protocol: Protocol {
//     _events: [Object: null prototype] {
//       data: [Function (anonymous)],
//       end: [Array],
//       handshake: [Function: bound _handleProtocolHandshake],
//       initialize: [Function: bound _handleProtocolInitialize],
//       unhandledError: [Function: bound ],
//       drain: [Function: bound ],
//       enqueue: [Function: bound _handleProtocolEnqueue]
//     },
//     _eventsCount: 7,
//     _maxListeners: undefined,
//     readable: true,
//     writable: true,
//     _config: ConnectionConfig {
//       host: 'ls-4bc51e1b7e7697cea034873d78dace84ee536579.cpfqei8aa9yx.ap-northeast-2.rds.amazonaws.com',
//       port: '3306',
//       localAddress: undefined,
//       socketPath: undefined,
//       user: 'carrot',
//       password: 'carrothater1991',
//       database: 'dbmaster',
//       connectTimeout: 10000,
//       insecureAuth: false,
//       supportBigNumbers: false,
//       bigNumberStrings: false,
//       dateStrings: false,
//       debug: undefined,
//       trace: true,
//       stringifyObjects: false,
//       timezone: 'local',
//       flags: '',
//       queryFormat: undefined,
//       pool: [Pool],
//       ssl: false,
//       localInfile: true,
//       multipleStatements: false,
//       typeCast: true,
//       maxPacketSize: 0,
//       charsetNumber: 33,
//       clientFlags: 455631,
//       protocol41: true
//     },
//     _connection: [Circular *2],
//     _callback: null,
//     _fatalError: null,
//     _quitSequence: null,
//     _handshake: true,
//     _handshaked: false,
//     _ended: false,
//     _destroyed: false,
//     _queue: [ [Handshake] ],
//     _handshakeInitializationPacket: HandshakeInitializationPacket {
//       protocolVersion: 10,
//       serverVersion: '8.0.33',
//       threadId: 305,
//       scrambleBuff1: <Buffer 13 56 4a 66 27 53 2a 29>,
//       filler1: <Buffer 00>,
//       serverCapabilities1: 65535,
//       serverLanguage: 255,
//       serverStatus: 2,
//       serverCapabilities2: 57343,
//       scrambleLength: 21,
//       filler2: <Buffer 00 00 00 00 00 00 00 00 00 00>,
//       scrambleBuff2: <Buffer 52 56 71 79 06 6d 1d 62 25 6d 4e 41>,
//       filler3: <Buffer 00>,
//       pluginData: 'mysql_native_password',
//       protocol41: true
//     },
//     _parser: Parser {
//       _supportBigNumbers: false,
//       _buffer: <Buffer 07 00 00 02 00 00 00 02 00 00 00>,
//       _nextBuffers: [BufferList],
//       _longPacketBuffers: [BufferList],
//       _offset: 11,
//       _packetEnd: 11,
//       _packetHeader: [PacketHeader],
//       _packetOffset: 4,
//       _onError: [Function: bound handleParserError],
//       _onPacket: [Function: bound ],
//       _nextPacketNumber: 3,
//       _encoding: 'utf-8',
//       _paused: false
//     },
//     [Symbol(kCapture)]: false
//   },
//   _connectCalled: true,
//   state: 'connected',
//   threadId: 305,
//   _pool: Pool {
//     _events: [Object: null prototype] {},
//     _eventsCount: 0,
//     _maxListeners: undefined,
//     config: PoolConfig {
//       acquireTimeout: 10000,
//       connectionConfig: [ConnectionConfig],
//       waitForConnections: true,
//       connectionLimit: 10,
//       queueLimit: 0
//     },
//     _acquiringConnections: [],
//     _allConnections: [ [Circular *2] ],
//     _freeConnections: [],
//     _connectionQueue: [],
//     _closed: false,
//     [Symbol(kCapture)]: false
//   },
//   [Symbol(kCapture)]: false
// }
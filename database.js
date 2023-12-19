import mysql from 'mysql';

const pool = function(conf) {
    const conn = mysql.createPool(conf);
    return conn;
};

const getConnect = async function(res, pool, queryString) {
    const query = queryString;
    
    await pool.getConnection((err, connection) => {
        if (err) {
            console.error('! CAN NOT CONNECT TO DATABASE ::', err);
            res.status(500).send({
                message: 'Server error : can not connect to database',
                data: err
            });
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
        });
    });
};

const postConnect = async function(res, pool, queryString) {
    const query = queryString;
    
    await pool.getConnection((err, connection) => {
        if (err) {
            console.error('! CAN NOT CONNECT TO DATABASE ::', err);
            res.status(500).send({
                message: 'Server error : can not connect to database',
                data: err
            });
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
        });
    });
};

const deleteConnect = async function(res, pool, queryString) {
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
                    res.status(401).send({
                        message: 'Authentication error: invalid username or password',
                        data: null
                    });
                    connection.release();
                }

                res.status(200).send({
                    message: '200 OK',
                    data: results
                });

                connection.release();
            });
        });
    } catch (err) {
        console.error('! CAN NOT CONNECT TO DATABASE ::', err);
        res.status(500).send({
            message: 'Server error : can not connect to database',
            data: err
        });
        return;
    }
};

export { pool, getConnect, postConnect, deleteConnect };

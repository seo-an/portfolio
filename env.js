let NODE_SERVER_PORT = null;
let mysqlHostConf = {};
let mysqlServerConf = {};
let API_INPUT_DATA_TO_THIS_TABLE = null;

if (process.env.NODE_ENV === 'local') {

	NODE_SERVER_PORT = process.env.NODE_LOCAL_PORT;
	mysqlServerConf = {
		host: process.env.MYSQL_CONF_LOCAL_SERVER_HOST,
		user: process.env.MYSQL_CONF_LOCAL_SERVER_USER,
		password: process.env.MYSQL_CONF_LOCAL_SERVER_PASSWORD,
		database: process.env.MYSQL_CONF_LOCAL_SERVER_DB,
		port: process.env.MYSQL_CONF_LOCAL_SERVER_PORT
	};

	// local database table name
	API_INPUT_DATA_TO_THIS_TABLE = process.env.DATABASE_TABLE_DEV_TEST;

} else if (process.env.NODE_ENV === 'staging') {

	NODE_SERVER_PORT = process.env.NODE_STAGING_PORT;

	// onStagingServerMysql
	mysqlServerConf = {
		host: process.env.MYSQL_CONF_STAGING_SERVER_HOST,
		user: process.env.MYSQL_CONF_STAGING_SERVER_USER,
		password: process.env.MYSQL_CONF_STAGING_SERVER_PASSWORD,
		database: process.env.MYSQL_CONF_STAGING_SERVER_DB,
		port: process.env.MYSQL_CONF_STAGING_SERVER_PORT
	};

	API_INPUT_DATA_TO_THIS_TABLE = process.env.DATABASE_TABLE_DEV_TEST;

} else if (process.env.NODE_ENV === 'production') {

	NODE_SERVER_PORT = process.env.NODE_PROD_PORT;

	// onProdServerMysql
	mysqlServerConf = {
		host: process.env.MYSQL_CONF_PROD_SERVER_HOST,
		user: process.env.MYSQL_CONF_PROD_SERVER_USER,
		password: process.env.MYSQL_CONF_PROD_SERVER_PASSWORD,
		database: process.env.MYSQL_CONF_PROD_SERVER_DB,
		port: process.env.MYSQL_CONF_PROD_SERVER_PORT,
	};

	// product database table name
	API_INPUT_DATA_TO_THIS_TABLE = process.env.DATABASE_TABLE_PROD_API;

}


module.exports = {
	NODE_SERVER_PORT,
	mysqlHostConf,
	mysqlServerConf,
	API_INPUT_DATA_TO_THIS_TABLE
};
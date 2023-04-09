// http-proxy-middleware 요청사항
// 반드시 /src 위치에 setupProxy.js 로 생성할 것
// App이 Proxy 서버를 사용하게 설정함
const { createProxyMiddleware } = require('http-proxy-middleware');

module.exports = function(app) {
	// console.log('❤❤');
  app.use('/weather-api', createProxyMiddleware({
		target: 'http://apis.data.go.kr',
		changeOrigin: true,
		timeout: 60000,
		pathRewrite: {
			'^/weather-api': ''
		}
	}));
};
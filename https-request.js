import https from 'https';
import { stringify } from 'querystring';

const externalRequestTo = (externalOptions, data) => {
	const reqData = stringify(data);

	return new Promise((resolve, reject) => {
		const externalReq = https.request(externalOptions, (externalRes) => {
			let resData = '';
	
			externalRes.on('data', (str) => {
				resData += str;
			});
	
			externalRes.on('end', () => {
				// console.log('Papago API Response:', resData);
				resolve(resData);
			});
		});
	
		externalReq.on('error', (error) => {
			console.error('ERROR! External Request ::', error);
			reject(error);
		});
	
		// 내부 요청에서 받은 데이터를 외부 서버로 전송
		externalReq.write(reqData);

		// 요청 마무리
		externalReq.end();
	});
};

export default externalRequestTo;
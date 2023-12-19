import { findExactWordByRegEx } from './withRegExDoFindWord.js';

export const copyToClipboard = async ( copyObj ) => {
    
	const envString = copyObj.browserEnv;
	const data = copyObj.data;
	const customErrorMessage = copyObj.errorMessage || '';

	const safariRegex = /Safari+/i;
	const chromeRegex = /Chrome+/i;

	try {
		// Safari
		if (findExactWordByRegEx(envString, safariRegex) && !findExactWordByRegEx(envString, chromeRegex)) {
			await navigator.clipboard.writeText(data);
			alert('클립보드에 복사되었습니다.');
			return;
		}
		
		// Chrome
		const permissionStatus = await navigator.permissions.query({ name: "clipboard-write" });
		if (permissionStatus.state === 'granted' || permissionStatus.state === 'prompt') {
			// 클립보드 권한이 이미 허용되어 있음
			// console.log('클립보드 권한이 이미 허용되어 있습니다.');
			await navigator.clipboard.writeText(data);
			alert('클립보드에 복사되었습니다.');
			return;
		} else {
			alert('권한이 없습니다.');
			return;
		}
		
	} catch (error) {
		console.error('Fail to load Cpilpboard API');
		alert('클립보드로 복사할 수 없습니다. '+customErrorMessage);
		return;
	}
};
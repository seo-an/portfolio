export const isThisNumber = (data) => {
	if (typeof(data) === 'number') return data || true;
	else {
		console.error('데이터가 숫자 형식이 아님 :: ', typeof(data));
		return false;
	}
};

export const isThisString = (data) => {
	if (typeof(data) === 'string' && (data.replace(/\s+/g, '')).length > 0) {
		return data || true;
	} else {
		console.error('데이터가 문자 형식이 아님 :: ', typeof(data));
		return false;
	}
};

export const isThisBoolean = (data) => {
	if (typeof(data) === 'boolean') return data || true;
	else {
		console.error('데이터가 불리언 형식이 아님 :: ', typeof(data));
		return false;
	}
};

export const isNotUndefined = (data) => {
	if (!(typeof(data) === 'undefined')) return data || true;
	else {
		console.error('undefined가 아님 :: ', typeof(data));
		return false;
	}
};

export const isNotNull = (data) => {
	if (!(data === null)) return data || true;
	else {
		console.error('데이터에 값이 존재하지 않음 :: ', data);
		return false;
	}
};

// export const isThisJSON = (data) => {
// 	console.log('1', typeof(data)==='object');
// 	if (typeof(data) === 'object' && data != null && JSON.stringify(data).replace(/\[\[\{|\}\]]/g, '').length > 0) {
// 		try {
// 			if (JSON.stringify(data) || JSON.parse(data)) {
// 				return true;
// 			}
// 		} catch (err) {
// 			console.error('데이터가 JSON 형식이 아님 :: ', err);
// 			return false;
// 		}
// 	} else {
// 		console.error('데이터가 JSON 형식이 아님 :: ', typeof(data));
// 		return false;
// 	}
// };
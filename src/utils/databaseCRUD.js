export const requestToDatabase = async (url, parameter) => {
	const queryString = new URLSearchParams(parameter).toString();
	console.log('test', `${url}?${queryString}`);
		try {
			const response = await fetch(`${url}?${queryString}`, {
				method: "GET",
			});

			if (!response.ok) {
				throw new Error('HTTP GET ERROR :: status ', response.status);
			}

			let result = await response.json();

			if (result.data.length === 0) {
				// database에 자료가 하나도 없을 때 예외처리
				return result = 'nothing';
			} else {
				// 최종
				return result.data;
			}

		} catch (error) {
			console.error('CAN NOT TRY TO FETCH :: ', error);

			const result = 'nothing';
			return result;

		}
};


export const postToDatabase = async (url, dat) => {
	const data = [dat];

	try {
		const response = await fetch(`${url}`, {
			method: "POST",
			headers: {
				"Content-Type": "application/json"
			},
			body: JSON.stringify(data)
		});

		if (!response.ok) {
			throw new Error('HTTP POST ERROR :: status ', response.status);
		}
		
		if (response.ok) {
			alert('방명록이 등록되었습니다. 신나요!');
		}

	} catch (error) {
		console.error('CAN NOT TRY TO FETCH :: ', error);
	}
};


export const deleteToDatabase = async (url, dat) => {
	const data = [dat];

	console.log('dd func', url, dat);

	// try {
	// 	const response = await fetch(`${url}`, {
	// 		method: "DELETE",
	// 		headers: {
	// 			"Content-Type": "application/json"
	// 		},
	// 		body: JSON.stringify(data)
	// 	});

	// 	if (!response.ok) {
	// 		throw new Error('HTTP POST ERROR :: status ', response.status);
	// 	}
		
	// 	if (response.ok) {
	// 		alert('삭제되었습니다.');
	// 	}

	// } catch (error) {
	// 	console.error('CAN NOT TRY TO FETCH :: ', error);
	// }
};
import { modalPopupDisallowClickOuterSpace, getPopupCoreMessage } from "./popup";

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

export const requestToDatabase = async (url, parameter) => {
	const queryString = new URLSearchParams(parameter).toString();

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

export const deleteInDatabase = async (url, dat) => {
	// const data = [dat]; // uniqueId
	const id = dat.uniqueId;

	getPopupCoreMessage(`
		<div style="display: flex;flex-wrap: wrap;justify-content: center;">
			<p>비밀번호를 입력해주세요</p>
			<input type="text" id="deleteToDatabase" placeholder="비밀번호"/>
		</div>
	`);

	console.log(document.querySelector('input#deleteToDatabase'));
	modalPopupDisallowClickOuterSpace();

	// 밑에는 삭제기능 완성된 것!
	// try {
	// 	const response = await fetch(`${url}/${id}`, {
  //     method: 'DELETE',
	// 	})

	// 	if (!response.ok) {
	// 		throw new Error('HTTP DELETE ERROR :: status ', response.status);
	// 	}
		
	// 	alert('삭제되었습니다.')

	// 	return new Date().getMilliseconds();

	// } catch (error) {
	// 	console.error('CAN NOT TRY TO FETCH :: ', error);
	// }
};



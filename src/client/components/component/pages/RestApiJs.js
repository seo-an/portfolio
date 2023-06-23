// import ;

// import { RestApiView } from "../../view/pages/RestApiView";

// import {  } from ;

import { useState, useEffect, useCallback, useMemo } from "react";

const getValue = (id) => {
	const getId = id;
	const getElement = document.getElementById(getId);
	const getValue = getElement.value;

	return getValue;
};

// const getFromDatabase = (parameter) => {
// 	const params = parameter;

// 	const queryString = new URLSearchParams(params).toString();

// 	const getData = async () => {
// 		try {
// 			const response = await fetch(`/api/data/get?${queryString}`, {
// 				method: "GET",
// 			});

// 			if (!response.ok) {
// 				throw new Error('HTTP GET ERROR :: status ', response.status);
// 			}

// 			const result = await response.json();

// 		} catch (error) {
// 			console.error('CAN NOT TRY TO FETCH :: ', error);
// 		}
// 	};

// 	getData();
// };


// const postToDatabase = (dat) => {
// 	const data = [dat];

// 	const postData = async () => {
// 		try {
// 			const response = await fetch(`/api/data/post`, {
// 				method: "POST",
// 				headers: {
// 					'Content-Type': 'application/json'
// 				},
// 				body: JSON.stringify(data)
// 			});

// 			if (!response.ok) {
// 				throw new Error('HTTP POST ERROR :: status ', response.status);
// 			}
			
// 			const result = response;
// 			console.log('post', result);

// 		} catch (error) {
// 			console.error('CAN NOT TRY TO FETCH :: ', error);
// 		}
// 	}

// 	postData();
// };


export const RestApiJs = () => {
	// const [data, setData] = useState('');
	const [getAndSave, setGetAndSave] = useState('');


	const unpack = (val) => {
		setGetAndSave(val);
	};


	const getFromDatabase = (parameter) => {
		const params = parameter;
	
		const queryString = new URLSearchParams(params).toString();
	
		const getData = async () => {
			try {
				const response = await fetch(`/api/data/get?${queryString}`, {
					method: "GET",
				});
	
				if (!response.ok) {
					throw new Error('HTTP GET ERROR :: status ', response.status);
				}
	
				const result = await response.json();
				unpack(result);
	
			} catch (error) {
				console.error('CAN NOT TRY TO FETCH :: ', error);
			}
		};
	
		getData();
	};
	

	const postToDatabase = (dat) => {
		const data = [dat];
	
		const postData = async () => {
			try {
				const response = await fetch(`/api/data/post`, {
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
		}
	
		postData();
	};


	const handleSubmit = async (e) => {
    e.preventDefault();

		const inputName = getValue('name');
		const inputPassword = getValue('simple_password');
		const inputComment = getValue('comment');

		const send = {
			'name': inputName,
			'simple_password': inputPassword,
			'comment': inputComment
		}

		// console.log('send', send);

		postToDatabase(send);
	};
  
	const getQuery = {
		'select': 'id, name, simple_password, comment, createdAt, lastUpdatedAt',
		'from': `${process.env.REACT_APP_DATABASE_TABLE_B}`,
		'where': ''
	};


	useEffect(() => {
		// 한 번만 로딩: missing dependency 무시
		getFromDatabase(getQuery);
	}, []);

	console.log(getAndSave);

  // return (
  //   <div>
  //     <h1>Posts</h1>
  //     {posts.map(post => (
  //       <div key={post.id}>
  //         <h2>{post.name}</h2>
  //         <p>{post.lastUpdatedAt}</p>
  //       </div>
  //     ))}
  //   </div>
  // );
	return (
    <div>
      <h1>방명록</h1>
			<form onSubmit={handleSubmit}>
				<div>
					<div>
						<input type="text" id="name" placeholder="이름"></input>
						<input type="text" id="simple_password" placeholder="비밀번호"></input>
						<input type="text" id="comment" placeholder="내용"></input>
					</div>
					<div>
						<button type="submit">등록</button>
					</div>
				</div>
			</form>
    </div>
  );

}

// export default RestApi;
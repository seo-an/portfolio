import { useState, useEffect } from 'react';

// import DATABASE_GET_RAW_TEST_DATA from '../data/database_get_raw_test_data.json';

import { RestApiInputForm } from '../../view/pages/RestApiInputForm.js';
import { RestApiResultDisplay } from '../../view/pages/RestApiResultDisplay.js';

import { getValue } from '../../action/actionsForRestApi.js';
import { requestToDatabase, postToDatabase, deleteInDatabase } from '../../../utils/withDatabaseDoCRUD.js';
import { descending } from '../../../utils/sort.js';
import { addClassRemoveClass } from '../../../utils/toggleClasses.js';


export const RestApiJs = () => {
	const [elements, setElements] = useState([]);
	const [trigger, setTrigger] = useState('');

	const url = '/api/guestbook/data';

	const handleSubmit = async (e) => {
    e.preventDefault();
		
		const inputName = getValue('name');
		const inputPassword = getValue('simple_password');
		const inputComment = getValue('comment');

		// console.log('wow', inputName, inputPassword, inputComment);

		if (inputName.length > 50) {
			return alert(`${inputName.length} 글자는 너무 길어서 이름으로 등록할 수 없어요. 50 글자 아래로 맞춰주세요.`);
		} else if (inputName.length === 0) {
			return alert(`이름을 입력해주세요.`);
		}

		if (inputPassword.length > 50) {
			return alert(`${inputPassword.length} 글자는 너무 길어서 패스워드로 등록할 수 없어요. 50 글자 아래로 맞춰주세요.`);
		} else if (inputPassword.length === 0) {
			return alert(`패스워드를 입력해주세요.`);
		}

		if (inputComment.length > 512) {
			return alert(`내용이 ${inputComment.length} 글자에요. 너무 길어서 등록할 수 없어요. 500 글자 아래로 맞춰주세요!`);
		} else if (inputComment.length === 0) {
			return alert(`내용을 입력해주세요.`);
		}

		const send = {
			'name': inputName,
			'simple_password': inputPassword,
			'comment': inputComment
		}

		postToDatabase(url, send);
		setTrigger(String(Math.random())+inputName);
	};

	const pageSize = 5;
	const paginationSize = 10;

	
	const clickList = (e, id) => {
		// id는 uniqueId
		const grandParent = e.currentTarget.closest('#paginationItems');
		const parent = e.currentTarget.closest('#guestbookList');

		const justClicked = addClassRemoveClass(grandParent, parent, 'selected');
		
		if (justClicked) {
			const _name = parent.querySelector('.forName').innerText;
			const _date = parent.querySelector('.forDate').innerText;
			const _comment = parent.querySelector('.forContent').innerText;

			const reg_name = /이름: (.+)/;
			const reg_date = /날짜: (.+)/;
			const reg_comment = /내용: (.+)/;

			const nowClicked = {
				uniqueId: id,
				name: reg_name.exec(_name)[1],
				createdAt: reg_date.exec(_date)[1],
				comment: reg_comment.exec(_comment)[1]
			}

			const deleteAction = deleteInDatabase(url, nowClicked);
			setTrigger(deleteAction);

		}
	}


	const setPageView = ( dat ) => {
		let raw = null;

		if (dat === 'nothing')  {
			// raw = DATABASE_GET_RAW_TEST_DATA;
			return setElements(dat);
		} else {
			raw = dat;
		};

		const len = raw.length;

		const cooking = raw.reduce((acc, curr, index) => {
			if (index < len) {
				acc.elements.push({name: curr.name, createdAt: curr.createdAt, comment: curr.comment});
				acc.classified.push({id: curr.uniqueId, pwd: curr.simple_password, lastUpdatedAt: curr.lastUpdatedAt});
				// console.log('1', curr.id, 'acc', acc, 'curr', curr.comment, 'index', index);
			} else {
				acc.elements.push({name: curr.name, createdAt: curr.createdAt, comment: curr.comment});
				acc.classified.push({id: curr.uniqueId, pwd: curr.simple_password, lastUpdatedAt: curr.lastUpdatedAt});
			}
			return acc;
		}, { elements: [], classified: [] });
		// console.log('cooking dinner', cooking);
		const cooked = [];
		let today = new Date();

		for (let i = 1; i < len + 1; i++) {
			cooked.push( (cooking.elements[i-1]) ? (<div className="guestBook" id="guestbookList" key={`${cooking.classified[i-1].id}`} onClick={(e) => clickList(e, cooking.classified[i-1].id)}>
				<input type="checkbox" name="checkbox"/>
				<div className="forName">이름: {cooking.elements[i-1].name}</div>
				<div className="forDate">날짜: {cooking.elements[i-1].createdAt}</div>
				<div className="forContent">내용: {cooking.elements[i-1].comment}</div>
			</div>) : null );
		}

		// console.log('dinner is serving', cooked);

		// raw data 넘기기
		return setElements(descending(cooked));
	};

	const goPagination = {
		data: elements,
		pageSize: pageSize,
		paginationSize: paginationSize
	};


	useEffect(() => {
		const cleaning = `DATE_FORMAT(createdAt, '%Y-%m-%d %H:%i:%s') AS createdAt`;
		// const getQuery = {
		// 	'select': `id, name, simple_password, comment, ${cleaning}, lastUpdatedAt`,
		// };
		const getQuery = {
			'select': `uniqueId, name, simple_password, comment, ${cleaning}, lastUpdatedAt`,
			'where': ``
		};

		requestToDatabase(url, getQuery).then((res) => setPageView(res));
	}, [trigger]);


	return (
		<>
			<RestApiResultDisplay props={ { ...goPagination } }/>
			<RestApiInputForm props={ handleSubmit }/>
		</>
	);

}
import styled from "styled-components";

import { useState } from "react";


export const GoFront = styled.a `
	display: flex;
	align-items: center;
	margin: 0px 16px 0px 8px;
	cursor: pointer;
`;
export const GoRear = styled.a `
	display: flex;
	align-items: center;
	margin: 0px 8px 0px 16px;
	cursor: pointer;
`;
export const Numbers = styled.a `
	margin: 4px;
	cursor: pointer;

	& span {
		display: flex;
		width: 24px;
		align-items: center;
		justify-content: center;
	}
`;
export const PaginationWrap = styled.div `
	display: flex;
	flex-wrap: nowrap;
	margin: 8px 0px;
`;

export const ContentsWrapper = styled.div `
	&.flight {
		display: flex;
		margin: 8px;

		& ul {
			margin: 8px 0px;
			& li {
				line-height: 1.6em;
			}
		}
	}

	&.guestBook {
		display: flex;
		margin: 8px 8px 16px 8px;
		flex-wrap: wrap;

		.forName {
			display: flex;
			width: 100%;
		}
	
		.forDate {
			display: flex;
			width: 100%;
		}
	
		.forContent {
			display: flex;
			margin-top: 4px;
			width: 100%;
		}
	}
`


export const cutOutItemsForPaging = (jsonData, dataLength) => {
	if (jsonData.length === 0) return [];
	const getData = jsonData;
	const criteria = dataLength;

	const resultContainer = [];

	const newArray = (data, num) => {
		if (data.length < num) return resultContainer.push(data);

		const arry = data.slice(0, num);
		const rest = data.slice(num, data.length);

		resultContainer.push(arry);
		if (rest.length === 0) return;
		return newArray(rest, num);
	}

	newArray(getData, criteria);

	return resultContainer;
};


export const Pagination = ( props ) => {
	// <Pagination> 컴포넌트
	// data={json} : 페이지네이션에 사용될 json 형식의 데이터 (cutOutItemsForPaging 함수로 array로 변형)
	// numOfItems={num} : 한 페이지에서 보여질 자료의 개수, 숫자로 받음
	// from={} : 페이지네이션 부르는 곳, 문자열로 받음
	const [pgNum, setPgNum] = useState(0);
	const [onPage, setOnPage] = useState(0);

	const called = props.from;

	const flightOrigin = (called === 'flight') ? ((props.data) ? props.data : []) : [];
	const flightDataPoints = (called === 'flight') ? (props.display) : 0;

	const guestBookOrigin = (called === 'guestBook') ? ((props.data) ? props.data : []) : [];
	const guestBookDataPoints = (called === 'guestBook') ? (props.display) : 0;

	const interval = (props.interval) ? props.interval : 10;
	
	const getPageNumber = (event) => {
		event.preventDefault();
		const val = (event.target.textContent) - 1;
		setPgNum(val);
		// console.log('in getPageNumber() : ', pgNum);
		return;
	};

	// const getNowOnNumber = (event) => {
	// 	event.preventDefault();
	// 	const id = event.target.id;
	// 	const criteria = Math.ceil((flightOrigin.length/flightDataPoints)/interval);
		
	// 	// console.log('now in getNowOnNumber() : ', onPage, pgNum, interval < pgNum);

	// 	if (id === 'prev') {
	// 		// console.log('prev', onPage, pgNum);
	// 		if (interval < pgNum) {
	// 			setPgNum(0);
	// 		}
	// 		if(criteria === onPage || criteria < onPage) {
	// 			const num = ((criteria - 2) < 0) ? 0 : (criteria - 2);
	// 			setOnPage(num);
	// 			setPgNum(0);
	// 			return;
	// 		}
	// 		if (onPage < 1) {
	// 			setOnPage(0); 
	// 			setPgNum(0); 
	// 			return;
	// 		} 
	// 		setOnPage(onPage - 1);
	// 		return;
	// 	} else if (id === 'next') {
	// 		if(criteria === onPage || criteria < onPage) {
	// 			setOnPage(criteria);
	// 			return;
	// 		}
	// 		// console.log('next', onPage, pgNum);
	// 		setOnPage(onPage + 1);
	// 		setPgNum(0);
	// 		return;
	// 	};
	// }


	const externalApi = ( data, pt, intv ) => {
		const original = data;
		const dataPoints = pt;
		const _interval = intv;
		const count = Math.ceil((original.length)/_interval);

		const numElements = [];
		const itemElements = [];
		const itemsElements = [];

		const forPagenationData = ( arryItem, arryNum ) => {
			const dataItem = arryItem;
			const dataNum = arryNum;
			const resultContainer = [];
			const reveal = [];

			const newArray = (data, num) => {
				if (data.length < num) return resultContainer.push(data);
		
				const arry = data.slice(0, num);
				const rest = data.slice(num, data.length);
		
				resultContainer.push(arry);
				if (rest.length === 0) return;
				return newArray(rest, num);
			};

			newArray(dataItem, _interval);
			newArray(dataNum, _interval);

			const array = resultContainer.reduce((acc, curr, index) => {
				if (index < count) {
					acc.forItems.push(curr);
				} else {
					acc.forPageNumbers.push(curr);
				}
				return acc;
			}, { forItems: [], forPageNumbers: [] });

			reveal[0] = array.forItems;
			reveal[1] = array.forPageNumbers;

			return reveal;
		};

		if (called === 'flight') {
			if (original === null) {
				return (numElements, itemsElements);
			} else {
				let today = new Date();
		
				for (let i = 0; i < original.length; i++) {
					numElements.push(<Numbers key={`num${i}`} onClick={getPageNumber}><span>{i+1}</span></Numbers>);

					for (let j = 0; j < dataPoints; j++) {
						itemElements[j] = (original[i][j]) ? (<ContentsWrapper className="flight" key={`item${j+1}+${j}+${today.getTime()}`}>
							<ul>
								<li>항공사: {original[i][j].airline}</li>
								<li>공항: {original[i][j].airport}</li>
								<li>상태: {original[i][j].remark}</li> 
							</ul>
						</ContentsWrapper>) : null;
			
						itemsElements[i] = [...itemElements];
					}
				}

				// console.log('in externalApi : /flight/ : ', numElements, itemsElements);
				const result = forPagenationData(itemsElements, numElements);
				return result;
			}
		}

		if (called === 'guestBook') {
			if (original === null) {
				return (numElements, itemsElements);
			} else {
				let today = new Date();
		
				for (let i = 0; i < original.length; i++) {
					numElements.push(<Numbers key={`num${i}`} onClick={getPageNumber}><span>{i+1}</span></Numbers>);

					for (let j = 0; j < dataPoints; j++) {
						itemElements[j] = (original[i][j]) ? (<ContentsWrapper className="guestBook" key={`item${j+1}+${j}+${today.getTime()}`}>
							<div className="forName">이름: {original[i][j].name}</div>
							<div className="forDate">날짜: {original[i][j].createdAt}</div> 
							<div className="forContent">내용: {original[i][j].comment}</div>
						</ContentsWrapper>) : null;
			
						itemsElements[i] = [...itemElements];
					}
				}

				// console.log('in externalApi : /flight/ : ', numElements, itemsElements);
				const result = forPagenationData(itemsElements, numElements);
				return result;
			}
		}

	};
	
	// const jsonToArray = cutOutItemsForPaging(flightOrigin, flightDataPoints);
	// const flightData = externalApi(jsonToArray, flightDataPoints, interval);
	// const back = (Math.ceil((flightOrigin.length/flightDataPoints)/interval) - 1);

	if (called === 'flight') {
		const jsonToArray = cutOutItemsForPaging(flightOrigin, flightDataPoints);
		const flightData = externalApi(jsonToArray, flightDataPoints, interval);
		const back = (Math.ceil((flightOrigin.length/flightDataPoints)/interval) - 1);

		const getNowOnNumber = (event) => {
			event.preventDefault();
			const id = event.target.id;
			const criteria = Math.ceil((flightOrigin.length/flightDataPoints)/interval);
			
			// console.log('now in getNowOnNumber() : ', onPage, pgNum, interval < pgNum);
	
			if (id === 'prev') {
				// console.log('prev', onPage, pgNum);
				if (interval < pgNum) {
					setPgNum(0);
				}
				if(criteria === onPage || criteria < onPage) {
					const num = ((criteria - 2) < 0) ? 0 : (criteria - 2);
					setOnPage(num);
					setPgNum(0);
					return;
				}
				if (onPage < 1) {
					setOnPage(0); 
					setPgNum(0); 
					return;
				} 
				setOnPage(onPage - 1);
				return;
			} else if (id === 'next') {
				if(criteria === onPage || criteria < onPage) {
					setOnPage(criteria);
					return;
				}
				// console.log('next', onPage, pgNum);
				setOnPage(onPage + 1);
				setPgNum(0);
				return;
			};
		}

		return (
			<>
				<div>
					{
						(onPage === (back+1)) ? 
							<>{flightData[0][back][pgNum]}</> : 
							( (pgNum > interval || pgNum === interval) ? 
								<>{flightData[0][onPage][(pgNum-(interval*onPage))]}</> : 
								<>{flightData[0][onPage][pgNum]}</> 
							)
					}
				</div>
				<PaginationWrap>
					<GoFront id="prev" onClick={getNowOnNumber}>{`<`}</GoFront>
						{(onPage === (back+1)) ? <>{flightData[1][back]}</> : <>{flightData[1][onPage]}</>}
					<GoRear id="next" onClick={getNowOnNumber}>{`>`}</GoRear>
				</PaginationWrap>
			</>
		);
	}


	if (called === 'guestBook') {
		const jsonToArray = cutOutItemsForPaging(guestBookOrigin, guestBookDataPoints);
		const guestBookData = externalApi(jsonToArray, guestBookDataPoints, interval);
		const back = (Math.ceil((guestBookOrigin.length/guestBookDataPoints)/interval) - 1);

		const getNowOnNumber = (event) => {
			event.preventDefault();
			const id = event.target.id;
			const criteria = Math.ceil((guestBookOrigin.length/guestBookDataPoints)/interval);
			
			// console.log('now in getNowOnNumber() : ', onPage, pgNum, interval < pgNum);
	
			if (id === 'prev') {
				// console.log('prev', onPage, pgNum);
				if (interval < pgNum) {
					setPgNum(0);
				}
				if(criteria === onPage || criteria < onPage) {
					const num = ((criteria - 2) < 0) ? 0 : (criteria - 2);
					setOnPage(num);
					setPgNum(0);
					return;
				}
				if (onPage < 1) {
					setOnPage(0); 
					setPgNum(0); 
					return;
				} 
				setOnPage(onPage - 1);
				return;
			} else if (id === 'next') {
				if(criteria === onPage || criteria < onPage) {
					setOnPage(criteria);
					return;
				}
				// console.log('next', onPage, pgNum);
				setOnPage(onPage + 1);
				setPgNum(0);
				return;
			};
		}

		console.log('test', jsonToArray, guestBookData);

		return (
			<>
				<div>
					{
						(onPage === (back+1)) ? 
							<>{guestBookData[0][back][pgNum]}</> : 
							( (pgNum > interval || pgNum === interval) ? 
								<>{guestBookData[0][onPage][(pgNum-(interval*onPage))]}</> : 
								<>{guestBookData[0][onPage][pgNum]}</> 
							)
					}
				</div>
				<PaginationWrap>
					<GoFront id="prev" onClick={getNowOnNumber}>{`<`}</GoFront>
						{(onPage === (back+1)) ? <>{guestBookData[1][back]}</> : <>{guestBookData[1][onPage]}</>}
					<GoRear class={`rear`} id="next" onClick={getNowOnNumber}>{`>`}</GoRear>
				</PaginationWrap>
			</>
		);
	}
};
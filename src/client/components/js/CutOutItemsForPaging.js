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

	&.selected {
		color: rgb(243, 114, 25, 1); //#f37219
		font-weight: bold;
	}

	& span {
		display: flex;
		width: 24px;
		align-items: center;
		justify-content: center;
	}
`;
export const PaginationWrap = styled.div `
	display: flex;
	width: 100%;
	padding: 16px 0px;
	justify-content: center;
	flex-wrap: nowrap;
`;
export const ContentsWrapper = styled.div `
	&.flight {
		display: flex;
		margin: 0px 8px;

		&:first-child {
			margin: 8px 8px 0px 8px;
		}

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

		&:first-child {
			margin: 16px 8px 16px 8px;
		}

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


export const cutOutItemsForPaging = (jsonData, dataLength, reverse) => {
	if (jsonData.length === 0) return [];
	const getData = (reverse === 'reverse') ? ([...jsonData].reverse()) : jsonData;
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

	const flightOrigin = (called === 'flight') ? ((props.data) ? props.data : null) : null;
	const flightDataPoints = (called === 'flight') ? (props.display) : 0;

	const guestBookOrigin = (called === 'guestBook') ? ((props.data) ? props.data : null) : null;
	const guestBookDataPoints = (called === 'guestBook') ? (props.display) : 0;

	const interval = (props.interval) ? props.interval : 10;


	const clearClass = ( element, label ) => {
		// element = 클래스를 적용할 단위
		
		if (element.parentElement) {
			console.log('here');
			const parent = element.parentElement;
			for (let i = 0; i < parent.children.length; i++) {
				// console.log('huh', parent.children[i].classList.contains(label));
				if (parent.children[i].classList.contains(label)) {
					// console.log('here', i);
					// parent.children[i].classList.remove(label);
					parent.children[i].classList.toggle(label);
				}
			}
		} else {
			return;
		}
		
	}


	const selectObj = ( element, label ) => {
		// console.log(element, label);
		const papa = (element.parentElement) ? element.parentElement : element;
		// const grandpa = element.parentElement.parentElement;

		clearClass(papa, label);
		// console.log('right', (clearClass(papa, 'selected')));

		papa.classList.add(label);

		
		// console.log('1', papa.classList.contains('selected'), grandpa.classList.contains('selected'))
		
		return;
	}
	
	const getPageNumber = (event) => {
		event.preventDefault();
		const el = event.target;
		const label = 'selected';
		const val = (el.textContent) - 1;
		setPgNum(val);

		selectObj (el, label);
		return;
	};


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
					if (i % _interval === 0) {
						numElements.push(<Numbers key={`num${i}`} className="selected" onClick={getPageNumber}><span>{i+1}</span></Numbers>);
					} else {
						numElements.push(<Numbers key={`num${i}`} onClick={getPageNumber}><span>{i+1}</span></Numbers>);
					}
					
					for (let j = 0; j < dataPoints; j++) {
						itemElements[j] = (original[i][j]) ? (<ContentsWrapper className="flight" key={`item${j+1}+${j}+${today.getTime()}`}>
							<ul>
								<li>항공편: {original[i][j].flightId}</li>
								<li>상태: {(original[i][j].remark) ? original[i][j].remark : '확인되지 않음'}</li> 
								<li>습도: {(original[i][j].himidity)? `${original[i][j].himidity}%` : '확인되지 않음'}</li>
								<li>풍속: {(original[i][j].wind)? `${original[i][j].wind}m/s` : '확인되지 않음'}</li>
								<li>관측 기온: {(original[i][j].temp)? `${original[i][j].temp}℃` : '확인되지 않음'}</li>
								<li>항공사: {original[i][j].airline}</li>
								<li>공항: {original[i][j].airport}</li>
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
					if (i % _interval === 0) {
						numElements.push(<Numbers key={`num${i}`} className="selected" onClick={getPageNumber}><span>{i+1}</span></Numbers>);
					} else {
						numElements.push(<Numbers key={`num${i}`} onClick={getPageNumber}><span>{i+1}</span></Numbers>);
					}
					// console.log(i%_interval);
					for (let j = 0; j < dataPoints; j++) {
						itemElements[j] = (original[i][j]) ? (<ContentsWrapper className="guestBook" key={`item${j+1}+${j}+${today.getTime()}`}>
							<div className="forName">이름: {original[i][j].name}</div>
							<div className="forDate">날짜: {original[i][j].createdAt}</div>
							<div className="forContent">내용: {original[i][j].comment}</div>
						</ContentsWrapper>) : null;
			
						itemsElements[i] = [...itemElements];
					}
				}

				// console.log('in externalApi : /guestBook/ : ', numElements, itemsElements);
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
		const originLength = Math.ceil(flightOrigin.length/flightDataPoints);
		const back = (Math.ceil((flightOrigin.length/flightDataPoints)/interval) - 1);

		const getNowOnPage = (event) => {
			event.preventDefault();
			const id = event.target.id;
			const criteria = Math.ceil((flightOrigin.length/flightDataPoints)/interval);
			
			// console.log('now in getNowOnPage() : ', onPage, pgNum, interval < pgNum);
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
				<>
					{
						(onPage === (back+1)) ? 
							<>{flightData[0][back][pgNum]}</> : 
							( (pgNum > interval || pgNum === interval) ? 
								<>{flightData[0][onPage][(pgNum-(interval*onPage))]}</> : 
								<>{flightData[0][onPage][pgNum]}</> 
							)
					}
				</>
				<PaginationWrap>
					{ (originLength < interval || originLength === interval) ? (
						<>
							{(onPage === (back+1)) ? <>{flightData[1][back]}</> : <>{flightData[1][onPage]}</>}
						</> ) : (
							(flightData.length > 0 && onPage === 0) ? (
								<>
									{(onPage === (back+1)) ? <>{flightData[1][back]}</> : <>{flightData[1][onPage]}</>}
									<GoRear class={`rear`} id="next" onClick={getNowOnPage}>{`>`}</GoRear>
								</> ) : (
									(onPage > 0 && onPage < flightData.length) ? (
										(flightData.length === flightData[0].length || flightData.length === flightData[1].length) ? (
											<>
											<GoFront id="prev" onClick={getNowOnPage}>{`<`}</GoFront>
												{(onPage === (back+1)) ? <>{flightData[1][back]}</> : <>{flightData[1][onPage]}</>}
											</>
										) : (
											<>
											<GoFront id="prev" onClick={getNowOnPage}>{`<`}</GoFront>
												{(onPage === (back+1)) ? <>{flightData[1][back]}</> : <>{flightData[1][onPage]}</>}
											<GoRear class={`rear`} id="next" onClick={getNowOnPage}>{`>`}</GoRear>
											</>
										)
									) : (
										<>
										<GoFront id="prev" onClick={getNowOnPage}>{`<`}</GoFront>
											{(onPage === (back+1)) ? <>{flightData[1][back]}</> : <>{flightData[1][onPage]}</>}
										</>
									)
							)
						)
					}
				</PaginationWrap>
			</>
		);
	}


	if (called === 'guestBook') {
		const jsonToArray = cutOutItemsForPaging(guestBookOrigin, guestBookDataPoints, 'reverse');
		const guestBookData = externalApi(jsonToArray, guestBookDataPoints, interval);
		const originLength = Math.ceil(guestBookOrigin.length/guestBookDataPoints);
		const back = (Math.ceil((guestBookOrigin.length/guestBookDataPoints)/interval) - 1);
		
		// console.log(guestBookData, originLength, interval, 
		// '전체 길이가 한 페이지 이하일 때 ',(originLength < interval || originLength === interval),
		// '마지막 페이지에 갔을 때', (onPage === guestBookData.length && guestBookData.length > 0),
		// '첫 번째 페이지에 있고 한 페이지 이상을 가지고 있을 때', (onPage === 0 && guestBookData.length > 0));
		
		const getNowOnPage = (event) => {
			event.preventDefault();
			const id = event.target.id;
			const criteria = Math.ceil((guestBookOrigin.length/guestBookDataPoints)/interval);

			// console.log('now in getNowOnPage() : ', onPage, pgNum, interval < pgNum);
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
				<>
					{
						(onPage === (back+1)) ? 
						<>{guestBookData[0][back][pgNum]}</> : 
						( (pgNum > interval || pgNum === interval) ? 
							<>{guestBookData[0][onPage][(pgNum-(interval*onPage))]}</> : 
							<>{guestBookData[0][onPage][pgNum]}</> 
						)
					}
				</>
				<PaginationWrap>
					{ (originLength < interval || originLength === interval) ? (
						<>
							{(onPage === (back+1)) ? <>{guestBookData[1][back]}</> : <>{guestBookData[1][onPage]}</>}
						</> ) : (
							(guestBookData.length > 0 && onPage === 0) ? (
								<>
									{(onPage === (back+1)) ? <>{guestBookData[1][back]}</> : <>{guestBookData[1][onPage]}</>}
									<GoRear class={`rear`} id="next" onClick={getNowOnPage}>{`>`}</GoRear>
								</> ) : (
									(onPage > 0 && onPage < guestBookData.length) ? (
										(guestBookData.length === guestBookData[0].length || guestBookData.length === guestBookData[1].length) ? (
											<>
											<GoFront id="prev" onClick={getNowOnPage}>{`<`}</GoFront>
												{(onPage === (back+1)) ? <>{guestBookData[1][back]}</> : <>{guestBookData[1][onPage]}</>}
											</>
										) : (
											<>
											<GoFront id="prev" onClick={getNowOnPage}>{`<`}</GoFront>
												{(onPage === (back+1)) ? <>{guestBookData[1][back]}</> : <>{guestBookData[1][onPage]}</>}
											<GoRear class={`rear`} id="next" onClick={getNowOnPage}>{`>`}</GoRear>
											</>
										)
									) : (
										<>
										<GoFront id="prev" onClick={getNowOnPage}>{`<`}</GoFront>
											{(onPage === (back+1)) ? <>{guestBookData[1][back]}</> : <>{guestBookData[1][onPage]}</>}
										</>
									)
							)
						)
					}
				</PaginationWrap>
			</>
		);
	}

	

};
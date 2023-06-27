import { useState } from "react";

export const cutOutItemsForPaging = (jsonData, dataLength) => {
	// console.log('json', jsonData.length === 0);
	if (jsonData.length === 0) return null;
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


// <Pagination> 컴포넌트
// data={json} : 페이지네이션에 사용될 json 형식의 데이터 (cutOutItemsForPaging 함수로 array로 변형)
// numOfItems={num} : 한 페이지에서 보여질 자료의 개수, 숫자로 받음
export const Pagination = ( props ) => {
	const [pgNum, setPgNum] = useState(0);

	const data = props.data;
	const dataPoints = props.numOfItems;

  const getPageNumber = (event) => {
    event.preventDefault();
    const val = event.target.textContent;

		setPgNum(val);

    return ;
  }

	// console.log('with useState : ', pgNum);
	const jsonToArray = cutOutItemsForPaging(data, dataPoints);
	
	const numElements = [];
	const itemElements = [];
	const itemsElements = [];

	if (jsonToArray === null) {
		return numElements, itemsElements;
	} else {
		let today = new Date();

		for (let i = 0; i < jsonToArray.length; i++) {
			numElements.push(<a key={`num${i}`} onClick={getPageNumber}>{i+1}</a>);
	
			for (let j = 0; j < dataPoints; j++) {
				itemElements[j] = (jsonToArray[i][j]) ? (<ul key={`item${j+1}+${j}+${today.getTime()}`}>
					<li>항공사: {jsonToArray[i][j].airline}</li>
					<li>공항: {jsonToArray[i][j].airport}</li>
					<li>상태: {jsonToArray[i][j].remark}</li> 
				</ul>) : null;
	
				itemsElements[i] = [...itemElements];
	
			}
	
		}
	}
	


	return (
		<>
			<div>
				{(pgNum === 0)? (itemsElements[0]) : (itemsElements[pgNum-1])}
			</div>
			<div>
				{numElements}
			</div>
		</>
	);
};
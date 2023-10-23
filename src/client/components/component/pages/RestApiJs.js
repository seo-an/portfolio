import { useState, useEffect } from "react";

import { RestApiView } from "../../view/pages/RestApiView";
import { Pagination } from "../../js/CutOutItemsForPaging";

const getValue = (id) => {
	const getId = id;
	const getElement = document.getElementById(getId);
	const getValue = getElement.value;

	return getValue;
};

// const getQuery = () => {
// 	const cleaning = `DATE_FORMAT(createdAt, '%Y-%m-%d %H:%i:%s') AS createdAt`;
// 	const getQuery = {
// 		'select': `id, name, simple_password, comment, ${cleaning}, lastUpdatedAt`,
// 		'from': `${process.env.REACT_APP_DATABASE_TABLE_B}`,
// 		'where': ''
// 	};

// 	return getQuery;
// }


export const RestApiJs = () => {
	const [elements, setElements] = useState([]);

	const getReady = ( dat ) => {
		const result = dat;
		// console.log(dat);
		if (result === null) {
			setElements(<></>);
			return;
		} else {
			setElements(<Pagination data={result} display={5} interval={10} from={`guestBook`} />);
			return;
		}
	};

	const getFromDatabase = (parameter) => {
		const params = parameter;
	
		const queryString = new URLSearchParams(params).toString();
	
		const getData = async () => {
			try {
				const response = await fetch(`/api/guestbook/data?${queryString}`, {
					method: "GET",
				});
	
				if (!response.ok) {
					throw new Error('HTTP GET ERROR :: status ', response.status);
				}
	
				let result = await response.json();

				if (result.length === 0) {
					// database에 자료가 하나도 없을 때 예외처리
					result = null;
				} else {
					getReady(result);
				}
				// getReady(result);
				
	
			} catch (error) {
				console.error('CAN NOT TRY TO FETCH :: ', error);
				const localTest = [
					{
							"id": 1,
							"name": "옥냥이",
							"simple_password": "옥옥123",
							"comment": "옥냥이의 리틀 호프",
							"createdAt": "2023-06-22 08:50:35",
							"lastUpdatedAt": "2023-06-21T23:50:35.000Z"
					},
					{
							"id": 2,
							"name": "옥냥이",
							"simple_password": "냥냥냥",
							"comment": "더 다크 픽쳐스 앤솔로지",
							"createdAt": "2023-06-22 08:53:57",
							"lastUpdatedAt": "2023-06-21T23:53:57.000Z"
					},
					{
							"id": 3,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 08:54:10",
							"lastUpdatedAt": "2023-06-21T23:54:10.000Z"
					},
					{
							"id": 4,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 08:55:28",
							"lastUpdatedAt": "2023-06-21T23:55:28.000Z"
					},
					{
							"id": 5,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:00:20",
							"lastUpdatedAt": "2023-06-22T00:00:20.000Z"
					},
					{
							"id": 6,
							"name": "옥냥이",
							"simple_password": "냥냥",
							"comment": "더 다크 픽쳐스 앤솔로지",
							"createdAt": "2023-06-22 09:00:50",
							"lastUpdatedAt": "2023-06-22T00:00:50.000Z"
					},
					{
							"id": 7,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:02:39",
							"lastUpdatedAt": "2023-06-22T00:02:39.000Z"
					},
					{
							"id": 8,
							"name": "",
							"simple_password": "",
							"comment": "",
							"createdAt": "2023-06-22 09:04:18",
							"lastUpdatedAt": "2023-06-22T00:04:18.000Z"
					},
					{
							"id": 9,
							"name": "옥냥이",
							"simple_password": "undefined",
							"comment": "더 다크 픽쳐스 앤솔로지",
							"createdAt": "2023-06-22 09:05:44",
							"lastUpdatedAt": "2023-06-22T00:05:44.000Z"
					},
					{
							"id": 10,
							"name": "옥냥이",
							"simple_password": "undefined",
							"comment": "더 다크 픽쳐스 앤솔로지",
							"createdAt": "2023-06-22 09:16:01",
							"lastUpdatedAt": "2023-06-22T00:16:01.000Z"
					},
					{
							"id": 11,
							"name": "옥냥이",
							"simple_password": "undefined",
							"comment": "더 다크 픽쳐스 앤솔로지",
							"createdAt": "2023-06-22 09:19:32",
							"lastUpdatedAt": "2023-06-22T00:19:32.000Z"
					},
					{
							"id": 12,
							"name": "옥냥이",
							"simple_password": "undefined",
							"comment": "더 다크 픽쳐스 앤솔로지",
							"createdAt": "2023-06-22 09:19:39",
							"lastUpdatedAt": "2023-06-22T00:19:39.000Z"
					},
					{
							"id": 13,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:19:44",
							"lastUpdatedAt": "2023-06-22T00:19:44.000Z"
					},
					{
							"id": 14,
							"name": "",
							"simple_password": "",
							"comment": "",
							"createdAt": "2023-06-22 09:19:48",
							"lastUpdatedAt": "2023-06-22T00:19:48.000Z"
					},
					{
							"id": 15,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-22 09:19:52",
							"lastUpdatedAt": "2023-06-22T00:19:52.000Z"
					},
					{
							"id": 16,
							"name": "옥냥이",
							"simple_password": "undefined",
							"comment": "더 다크 픽쳐스 앤솔로지",
							"createdAt": "2023-06-22 09:21:22",
							"lastUpdatedAt": "2023-06-22T00:21:22.000Z"
					},
					{
							"id": 17,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:21:26",
							"lastUpdatedAt": "2023-06-22T00:21:26.000Z"
					},
					{
							"id": 18,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:21:26",
							"lastUpdatedAt": "2023-06-22T00:21:26.000Z"
					},
					{
							"id": 19,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-22 09:21:31",
							"lastUpdatedAt": "2023-06-22T00:21:31.000Z"
					},
					{
							"id": 20,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-22 09:21:32",
							"lastUpdatedAt": "2023-06-22T00:21:32.000Z"
					},
					{
							"id": 21,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:22:36",
							"lastUpdatedAt": "2023-06-22T00:22:36.000Z"
					},
					{
							"id": 22,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:22:36",
							"lastUpdatedAt": "2023-06-22T00:22:36.000Z"
					},
					{
							"id": 23,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-22 09:22:40",
							"lastUpdatedAt": "2023-06-22T00:22:40.000Z"
					},
					{
							"id": 24,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-22 09:22:40",
							"lastUpdatedAt": "2023-06-22T00:22:40.000Z"
					},
					{
							"id": 25,
							"name": "",
							"simple_password": "",
							"comment": "",
							"createdAt": "2023-06-22 09:23:46",
							"lastUpdatedAt": "2023-06-22T00:23:46.000Z"
					},
					{
							"id": 26,
							"name": "",
							"simple_password": "",
							"comment": "",
							"createdAt": "2023-06-22 09:23:46",
							"lastUpdatedAt": "2023-06-22T00:23:46.000Z"
					},
					{
							"id": 27,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:24:57",
							"lastUpdatedAt": "2023-06-22T00:24:57.000Z"
					},
					{
							"id": 28,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:24:57",
							"lastUpdatedAt": "2023-06-22T00:24:57.000Z"
					},
					{
							"id": 29,
							"name": "",
							"simple_password": "",
							"comment": "",
							"createdAt": "2023-06-22 09:24:59",
							"lastUpdatedAt": "2023-06-22T00:24:59.000Z"
					},
					{
							"id": 30,
							"name": "",
							"simple_password": "",
							"comment": "",
							"createdAt": "2023-06-22 09:24:59",
							"lastUpdatedAt": "2023-06-22T00:24:59.000Z"
					},
					{
							"id": 31,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:25:20",
							"lastUpdatedAt": "2023-06-22T00:25:20.000Z"
					},
					{
							"id": 32,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:25:20",
							"lastUpdatedAt": "2023-06-22T00:25:20.000Z"
					},
					{
							"id": 33,
							"name": "",
							"simple_password": "",
							"comment": "",
							"createdAt": "2023-06-22 09:25:21",
							"lastUpdatedAt": "2023-06-22T00:25:21.000Z"
					},
					{
							"id": 34,
							"name": "",
							"simple_password": "",
							"comment": "",
							"createdAt": "2023-06-22 09:25:21",
							"lastUpdatedAt": "2023-06-22T00:25:21.000Z"
					},
					{
							"id": 35,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:25:51",
							"lastUpdatedAt": "2023-06-22T00:25:51.000Z"
					},
					{
							"id": 36,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:25:51",
							"lastUpdatedAt": "2023-06-22T00:25:51.000Z"
					},
					{
							"id": 37,
							"name": "1212",
							"simple_password": "1212",
							"comment": "1212",
							"createdAt": "2023-06-22 09:25:57",
							"lastUpdatedAt": "2023-06-22T00:25:57.000Z"
					},
					{
							"id": 38,
							"name": "1212",
							"simple_password": "1212",
							"comment": "1212",
							"createdAt": "2023-06-22 09:25:57",
							"lastUpdatedAt": "2023-06-22T00:25:57.000Z"
					},
					{
							"id": 39,
							"name": "옥냥이",
							"simple_password": "undefined",
							"comment": "더 다크 픽쳐스 앤솔로지",
							"createdAt": "2023-06-22 09:30:30",
							"lastUpdatedAt": "2023-06-22T00:30:30.000Z"
					},
					{
							"id": 40,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:30:35",
							"lastUpdatedAt": "2023-06-22T00:30:35.000Z"
					},
					{
							"id": 41,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:30:35",
							"lastUpdatedAt": "2023-06-22T00:30:35.000Z"
					},
					{
							"id": 42,
							"name": "12",
							"simple_password": "23",
							"comment": "34",
							"createdAt": "2023-06-22 09:30:43",
							"lastUpdatedAt": "2023-06-22T00:30:43.000Z"
					},
					{
							"id": 43,
							"name": "12",
							"simple_password": "23",
							"comment": "34",
							"createdAt": "2023-06-22 09:30:43",
							"lastUpdatedAt": "2023-06-22T00:30:43.000Z"
					},
					{
							"id": 44,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:31:25",
							"lastUpdatedAt": "2023-06-22T00:31:25.000Z"
					},
					{
							"id": 45,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:31:25",
							"lastUpdatedAt": "2023-06-22T00:31:25.000Z"
					},
					{
							"id": 46,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:43:51",
							"lastUpdatedAt": "2023-06-22T00:43:51.000Z"
					},
					{
							"id": 47,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:45:51",
							"lastUpdatedAt": "2023-06-22T00:45:51.000Z"
					},
					{
							"id": 48,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:46:40",
							"lastUpdatedAt": "2023-06-22T00:46:40.000Z"
					},
					{
							"id": 49,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:46:40",
							"lastUpdatedAt": "2023-06-22T00:46:40.000Z"
					},
					{
							"id": 50,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:48:02",
							"lastUpdatedAt": "2023-06-22T00:48:02.000Z"
					},
					{
							"id": 51,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:48:02",
							"lastUpdatedAt": "2023-06-22T00:48:02.000Z"
					},
					{
							"id": 52,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:53:02",
							"lastUpdatedAt": "2023-06-22T00:53:02.000Z"
					},
					{
							"id": 53,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:53:02",
							"lastUpdatedAt": "2023-06-22T00:53:02.000Z"
					},
					{
							"id": 54,
							"name": "11",
							"simple_password": "1",
							"comment": "1",
							"createdAt": "2023-06-22 09:53:42",
							"lastUpdatedAt": "2023-06-22T00:53:42.000Z"
					},
					{
							"id": 55,
							"name": "11",
							"simple_password": "1",
							"comment": "1",
							"createdAt": "2023-06-22 09:53:42",
							"lastUpdatedAt": "2023-06-22T00:53:42.000Z"
					},
					{
							"id": 56,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:53:53",
							"lastUpdatedAt": "2023-06-22T00:53:53.000Z"
					},
					{
							"id": 57,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:53:53",
							"lastUpdatedAt": "2023-06-22T00:53:53.000Z"
					},
					{
							"id": 58,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:55:46",
							"lastUpdatedAt": "2023-06-22T00:55:46.000Z"
					},
					{
							"id": 59,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 09:55:46",
							"lastUpdatedAt": "2023-06-22T00:55:46.000Z"
					},
					{
							"id": 60,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:03:16",
							"lastUpdatedAt": "2023-06-22T01:03:16.000Z"
					},
					{
							"id": 61,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:03:16",
							"lastUpdatedAt": "2023-06-22T01:03:16.000Z"
					},
					{
							"id": 62,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:07:20",
							"lastUpdatedAt": "2023-06-22T01:07:20.000Z"
					},
					{
							"id": 63,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:07:20",
							"lastUpdatedAt": "2023-06-22T01:07:20.000Z"
					},
					{
							"id": 64,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:08:32",
							"lastUpdatedAt": "2023-06-22T01:08:32.000Z"
					},
					{
							"id": 65,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:08:32",
							"lastUpdatedAt": "2023-06-22T01:08:32.000Z"
					},
					{
							"id": 66,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:09:22",
							"lastUpdatedAt": "2023-06-22T01:09:22.000Z"
					},
					{
							"id": 67,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:09:22",
							"lastUpdatedAt": "2023-06-22T01:09:22.000Z"
					},
					{
							"id": 68,
							"name": "11",
							"simple_password": "22",
							"comment": "33",
							"createdAt": "2023-06-22 10:10:32",
							"lastUpdatedAt": "2023-06-22T01:10:32.000Z"
					},
					{
							"id": 69,
							"name": "11",
							"simple_password": "22",
							"comment": "33",
							"createdAt": "2023-06-22 10:10:32",
							"lastUpdatedAt": "2023-06-22T01:10:32.000Z"
					},
					{
							"id": 70,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:10:45",
							"lastUpdatedAt": "2023-06-22T01:10:45.000Z"
					},
					{
							"id": 71,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:10:45",
							"lastUpdatedAt": "2023-06-22T01:10:45.000Z"
					},
					{
							"id": 72,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:12:15",
							"lastUpdatedAt": "2023-06-22T01:12:15.000Z"
					},
					{
							"id": 73,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:12:15",
							"lastUpdatedAt": "2023-06-22T01:12:15.000Z"
					},
					{
							"id": 74,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:12:15",
							"lastUpdatedAt": "2023-06-22T01:12:15.000Z"
					},
					{
							"id": 75,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:12:15",
							"lastUpdatedAt": "2023-06-22T01:12:15.000Z"
					},
					{
							"id": 76,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-22 10:21:39",
							"lastUpdatedAt": "2023-06-22T01:21:39.000Z"
					},
					{
							"id": 77,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-22 10:21:39",
							"lastUpdatedAt": "2023-06-22T01:21:39.000Z"
					},
					{
							"id": 78,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-22 10:21:39",
							"lastUpdatedAt": "2023-06-22T01:21:39.000Z"
					},
					{
							"id": 79,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-22 10:21:39",
							"lastUpdatedAt": "2023-06-22T01:21:39.000Z"
					},
					{
							"id": 80,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:22:50",
							"lastUpdatedAt": "2023-06-22T01:22:50.000Z"
					},
					{
							"id": 81,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:22:50",
							"lastUpdatedAt": "2023-06-22T01:22:50.000Z"
					},
					{
							"id": 82,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-22 10:23:32",
							"lastUpdatedAt": "2023-06-22T01:23:32.000Z"
					},
					{
							"id": 83,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-22 10:23:32",
							"lastUpdatedAt": "2023-06-22T01:23:32.000Z"
					},
					{
							"id": 84,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:28:05",
							"lastUpdatedAt": "2023-06-22T01:28:05.000Z"
					},
					{
							"id": 85,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:28:05",
							"lastUpdatedAt": "2023-06-22T01:28:05.000Z"
					},
					{
							"id": 86,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:29:14",
							"lastUpdatedAt": "2023-06-22T01:29:14.000Z"
					},
					{
							"id": 87,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:29:14",
							"lastUpdatedAt": "2023-06-22T01:29:14.000Z"
					},
					{
							"id": 88,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:31:13",
							"lastUpdatedAt": "2023-06-22T01:31:13.000Z"
					},
					{
							"id": 89,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:31:13",
							"lastUpdatedAt": "2023-06-22T01:31:13.000Z"
					},
					{
							"id": 90,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:31:49",
							"lastUpdatedAt": "2023-06-22T01:31:49.000Z"
					},
					{
							"id": 91,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:31:49",
							"lastUpdatedAt": "2023-06-22T01:31:49.000Z"
					},
					{
							"id": 92,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:33:54",
							"lastUpdatedAt": "2023-06-22T01:33:54.000Z"
					},
					{
							"id": 93,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:33:54",
							"lastUpdatedAt": "2023-06-22T01:33:54.000Z"
					},
					{
							"id": 94,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:51:13",
							"lastUpdatedAt": "2023-06-22T01:51:13.000Z"
					},
					{
							"id": 95,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:51:13",
							"lastUpdatedAt": "2023-06-22T01:51:13.000Z"
					},
					{
							"id": 96,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 10:57:04",
							"lastUpdatedAt": "2023-06-22T01:57:04.000Z"
					},
					{
							"id": 97,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 12:35:59",
							"lastUpdatedAt": "2023-06-22T03:35:59.000Z"
					},
					{
							"id": 98,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 12:39:31",
							"lastUpdatedAt": "2023-06-22T03:39:31.000Z"
					},
					{
							"id": 99,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 12:42:05",
							"lastUpdatedAt": "2023-06-22T03:42:05.000Z"
					},
					{
							"id": 100,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 12:43:26",
							"lastUpdatedAt": "2023-06-22T03:43:26.000Z"
					},
					{
							"id": 101,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 12:44:45",
							"lastUpdatedAt": "2023-06-22T03:44:45.000Z"
					},
					{
							"id": 102,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 12:45:09",
							"lastUpdatedAt": "2023-06-22T03:45:09.000Z"
					},
					{
							"id": 103,
							"name": "옥냥이",
							"simple_password": "undefined",
							"comment": "더 다크 픽쳐스 앤솔로지",
							"createdAt": "2023-06-22 12:45:54",
							"lastUpdatedAt": "2023-06-22T03:45:54.000Z"
					},
					{
							"id": 104,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 12:47:45",
							"lastUpdatedAt": "2023-06-22T03:47:45.000Z"
					},
					{
							"id": 105,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 12:50:58",
							"lastUpdatedAt": "2023-06-22T03:50:58.000Z"
					},
					{
							"id": 106,
							"name": "옥냥이",
							"simple_password": "undefined",
							"comment": "더 다크 픽쳐스 앤솔로지",
							"createdAt": "2023-06-22 13:04:22",
							"lastUpdatedAt": "2023-06-22T04:04:22.000Z"
					},
					{
							"id": 107,
							"name": "옥냥이",
							"simple_password": "undefined",
							"comment": "더 다크 픽쳐스 앤솔로지",
							"createdAt": "2023-06-22 13:05:23",
							"lastUpdatedAt": "2023-06-22T04:05:23.000Z"
					},
					{
							"id": 108,
							"name": "옥냥이",
							"simple_password": "undefined",
							"comment": "더 다크 픽쳐스 앤솔로지",
							"createdAt": "2023-06-22 13:06:29",
							"lastUpdatedAt": "2023-06-22T04:06:29.000Z"
					},
					{
							"id": 109,
							"name": "옥냥이",
							"simple_password": "undefined",
							"comment": "더 다크 픽쳐스 앤솔로지",
							"createdAt": "2023-06-22 13:06:40",
							"lastUpdatedAt": "2023-06-22T04:06:40.000Z"
					},
					{
							"id": 110,
							"name": "옥냥이",
							"simple_password": "옥냥옥냥",
							"comment": "더 다크 픽쳐스 앤솔로지",
							"createdAt": "2023-06-22 13:07:07",
							"lastUpdatedAt": "2023-06-22T04:07:07.000Z"
					},
					{
							"id": 111,
							"name": "1",
							"simple_password": "undefined",
							"comment": "3",
							"createdAt": "2023-06-22 13:07:40",
							"lastUpdatedAt": "2023-06-22T04:07:40.000Z"
					},
					{
							"id": 112,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 13:07:49",
							"lastUpdatedAt": "2023-06-22T04:07:49.000Z"
					},
					{
							"id": 113,
							"name": "1",
							"simple_password": "undefined",
							"comment": "3",
							"createdAt": "2023-06-22 13:08:25",
							"lastUpdatedAt": "2023-06-22T04:08:25.000Z"
					},
					{
							"id": 114,
							"name": "111",
							"simple_password": "undefined",
							"comment": "311",
							"createdAt": "2023-06-22 13:08:31",
							"lastUpdatedAt": "2023-06-22T04:08:31.000Z"
					},
					{
							"id": 115,
							"name": "undefined",
							"simple_password": "undefined",
							"comment": "undefined",
							"createdAt": "2023-06-22 13:09:58",
							"lastUpdatedAt": "2023-06-22T04:09:58.000Z"
					},
					{
							"id": 116,
							"name": "옥냥이",
							"simple_password": "옥냥옥냥",
							"comment": "더 다크 픽쳐스 앤솔로지",
							"createdAt": "2023-06-22 13:14:37",
							"lastUpdatedAt": "2023-06-22T04:14:37.000Z"
					},
					{
							"id": 117,
							"name": "",
							"simple_password": "",
							"comment": "",
							"createdAt": "2023-06-23 15:07:48",
							"lastUpdatedAt": "2023-06-23T06:07:48.000Z"
					},
					{
							"id": 118,
							"name": "1",
							"simple_password": "",
							"comment": "",
							"createdAt": "2023-06-23 15:08:36",
							"lastUpdatedAt": "2023-06-23T06:08:36.000Z"
					},
					{
							"id": 119,
							"name": "1",
							"simple_password": "1",
							"comment": "1",
							"createdAt": "2023-06-23 15:10:35",
							"lastUpdatedAt": "2023-06-23T06:10:35.000Z"
					},
					{
							"id": 120,
							"name": "hi",
							"simple_password": "hi",
							"comment": "hi",
							"createdAt": "2023-06-23 15:13:40",
							"lastUpdatedAt": "2023-06-23T06:13:40.000Z"
					},
					{
							"id": 121,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-23 15:17:09",
							"lastUpdatedAt": "2023-06-23T06:17:09.000Z"
					},
					{
							"id": 122,
							"name": "11",
							"simple_password": "22",
							"comment": "33",
							"createdAt": "2023-06-23 15:19:50",
							"lastUpdatedAt": "2023-06-23T06:19:50.000Z"
					},
					{
							"id": 123,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-23 15:45:23",
							"lastUpdatedAt": "2023-06-23T06:45:23.000Z"
					},
					{
							"id": 124,
							"name": "1212",
							"simple_password": "2323",
							"comment": "123123",
							"createdAt": "2023-06-23 16:27:07",
							"lastUpdatedAt": "2023-06-23T07:27:07.000Z"
					},
					{
							"id": 125,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-23 17:37:11",
							"lastUpdatedAt": "2023-06-23T08:37:11.000Z"
					},
					{
							"id": 126,
							"name": "11",
							"simple_password": "22",
							"comment": "33",
							"createdAt": "2023-06-23 17:41:49",
							"lastUpdatedAt": "2023-06-23T08:41:49.000Z"
					},
					{
							"id": 127,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-23 18:03:31",
							"lastUpdatedAt": "2023-06-23T09:03:31.000Z"
					},
					{
							"id": 128,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-23 18:06:26",
							"lastUpdatedAt": "2023-06-23T09:06:26.000Z"
					},
					{
							"id": 129,
							"name": "된",
							"simple_password": "거",
							"comment": "냐",
							"createdAt": "2023-06-23 18:06:46",
							"lastUpdatedAt": "2023-06-23T09:06:46.000Z"
					},
					{
							"id": 130,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-24 07:01:14",
							"lastUpdatedAt": "2023-06-23T22:01:14.000Z"
					},
					{
							"id": 131,
							"name": "이건",
							"simple_password": "폰에서",
							"comment": "테스트",
							"createdAt": "2023-06-24 08:04:53",
							"lastUpdatedAt": "2023-06-23T23:04:53.000Z"
					},
					{
							"id": 132,
							"name": "q",
							"simple_password": "w",
							"comment": "e",
							"createdAt": "2023-06-25 15:32:00",
							"lastUpdatedAt": "2023-06-25T06:32:00.000Z"
					},
					{
							"id": 133,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-25 15:54:37",
							"lastUpdatedAt": "2023-06-25T06:54:37.000Z"
					},
					{
							"id": 134,
							"name": "fh",
							"simple_password": "zjf",
							"comment": "ghtmxm",
							"createdAt": "2023-06-25 17:41:19",
							"lastUpdatedAt": "2023-06-25T08:41:19.000Z"
					},
					{
							"id": 135,
							"name": "hi",
							"simple_password": "hi",
							"comment": "hi",
							"createdAt": "2023-06-25 17:41:53",
							"lastUpdatedAt": "2023-06-25T08:41:53.000Z"
					},
					{
							"id": 136,
							"name": "아농하새료",
							"simple_password": "댜댜",
							"comment": "정말멋져요",
							"createdAt": "2023-06-28 04:33:30",
							"lastUpdatedAt": "2023-06-27T19:33:30.000Z"
					},
					{
							"id": 137,
							"name": "1",
							"simple_password": "2",
							"comment": "3",
							"createdAt": "2023-06-28 16:57:08",
							"lastUpdatedAt": "2023-06-28T07:57:08.000Z"
					}
			];

				getReady(localTest);
				// console.log('saved data');
			}
		};
	
		getData();
	};
	

	const postToDatabase = (dat) => {
		const data = [dat];
	
		const postData = async () => {
			try {
				const response = await fetch(`/api/guestbook/data`, {
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

	const cleaning = `DATE_FORMAT(createdAt, '%Y-%m-%d %H:%i:%s') AS createdAt`;
	let getQuery = '';

	if (process.env.REACT_APP_NODE_ENV === 'production') {
		// for real data
		getQuery = {
			'select': `id, name, simple_password, comment, ${cleaning}, lastUpdatedAt`,
			'from': `${process.env.REACT_APP_DATABASE_TABLE_PROD_API}`,
			'where': ''
		};
	} else {
		// for test data
		getQuery = {
			'select': `id, name, simple_password, comment, ${cleaning}, lastUpdatedAt`,
			'from': `${process.env.REACT_APP_DATABASE_TABLE_DEV_TEST}`,
			'where': ''
		};
	}
	
	

	const handleSubmit = async (e) => {
    e.preventDefault();

		const inputName = getValue('name');
		const inputPassword = getValue('simple_password');
		const inputComment = getValue('comment');

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

		// console.log('send', send);

		postToDatabase(send);
		getFromDatabase(getQuery);
	};
  

	useEffect(() => {
		// 한 번만 로딩: missing dependency 무시
		getFromDatabase(getQuery);
	}, []);


	const toRestApiViewProps = {
    handleSubmit,
    elements,
  }
	

	return (
		<RestApiView props={ toRestApiViewProps }/>
  );

}
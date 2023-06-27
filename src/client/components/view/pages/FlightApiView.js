import styled from "styled-components";

import { ReactComponent as AirplaneSVG } from "../icon/svg/airplane.svg";
import airlinesInfo from "../../data/AirlinesInfo.json"
import { Pagination } from "../../component/pages/CutOutItemsForPaging.js";


export const Container = styled.div `
  display: flex;
  margin: 32px 16px;
  flex-wrap: wrap;
`;

export const Title = styled.h1 `
  font-size: 1.8em;
`;

export const Wrapper = styled.div `
  display: flex;
  margin: 16px 16px;
  flex-wrap: wrap;
`;

export const Conetent = styled.div `
display: block;

& ul {
  margin: 16px 0;
  & li {
    line-height: 1.4em;
  }
}
`;

export const FlightApiView = ( fromFlightApiJs ) => {
  const airlines = airlinesInfo.airline;
  const airports = airlinesInfo.airport;

  fromFlightApiJs.props.getFlightApiData(airlinesInfo);
  
  const finalData = (fromFlightApiJs.props.final === undefined) ? {items: []} : fromFlightApiJs.props.final;
  let result = finalData.items;
  console.log('result', result);


  const ex = [
    {
        "airline": "비엣젯항공",
        "flightId": "VJ926",
        "scheduleDateTime": "0615",
        "estimatedDateTime": "0551",
        "airport": "하이퐁",
        "gatenumber": "124",
        "carousel": "13",
        "exitnumber": "D",
        "remark": "도착",
        "airportCode": "HPH",
        "yoil": null,
        "himidity": null,
        "wind": null,
        "temp": null,
        "senstemp": null,
        "wimage": null,
        "terminalid": "P02"
    },
    {
        "airline": "비엣젯항공",
        "flightId": "VJ864",
        "scheduleDateTime": "0545",
        "estimatedDateTime": "0554",
        "airport": "호찌민",
        "gatenumber": "122",
        "carousel": "14",
        "exitnumber": "D",
        "remark": "도착",
        "airportCode": "SGN",
        "yoil": "화",
        "himidity": "72",
        "wind": "1.5",
        "temp": "30.5",
        "senstemp": "36.8",
        "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon04",
        "terminalid": "P02"
    },
    {
        "airline": "델타항공",
        "flightId": "DL7927",
        "scheduleDateTime": "0640",
        "estimatedDateTime": "0601",
        "airport": "치앙마이",
        "gatenumber": "241",
        "carousel": "4",
        "exitnumber": "A",
        "remark": "도착",
        "airportCode": "CNX",
        "yoil": null,
        "himidity": null,
        "wind": null,
        "temp": null,
        "senstemp": null,
        "wimage": null,
        "terminalid": "P03"
    },
    {
        "airline": "대한항공",
        "flightId": "KE668",
        "scheduleDateTime": "0640",
        "estimatedDateTime": "0601",
        "airport": "치앙마이",
        "gatenumber": "241",
        "carousel": "4",
        "exitnumber": "A",
        "remark": "도착",
        "airportCode": "CNX",
        "yoil": null,
        "himidity": null,
        "wind": null,
        "temp": null,
        "senstemp": null,
        "wimage": null,
        "terminalid": "P03"
    },
    {
        "airline": "비엣젯항공",
        "flightId": "VJ878",
        "scheduleDateTime": "0600",
        "estimatedDateTime": "0603",
        "airport": "다낭",
        "gatenumber": "132",
        "carousel": "12",
        "exitnumber": "D",
        "remark": "도착",
        "airportCode": "DAD",
        "yoil": null,
        "himidity": null,
        "wind": null,
        "temp": null,
        "senstemp": null,
        "wimage": null,
        "terminalid": "P02"
    },
    {
        "airline": "한 에어",
        "flightId": "H19781",
        "scheduleDateTime": "0550",
        "estimatedDateTime": "0604",
        "airport": "치앙마이",
        "gatenumber": "103",
        "carousel": "9",
        "exitnumber": "C",
        "remark": "도착",
        "airportCode": "CNX",
        "yoil": null,
        "himidity": null,
        "wind": null,
        "temp": null,
        "senstemp": null,
        "wimage": null,
        "terminalid": "P02"
    },
    {
        "airline": "제주항공",
        "flightId": "7C4206",
        "scheduleDateTime": "0550",
        "estimatedDateTime": "0604",
        "airport": "치앙마이",
        "gatenumber": "103",
        "carousel": "9",
        "exitnumber": "C",
        "remark": "도착",
        "airportCode": "CNX",
        "yoil": null,
        "himidity": null,
        "wind": null,
        "temp": null,
        "senstemp": null,
        "wimage": null,
        "terminalid": "P02"
    },
    {
        "airline": "에어아시아엑스",
        "flightId": "D7504",
        "scheduleDateTime": "0630",
        "estimatedDateTime": "0603",
        "airport": "쿠알라룸푸르",
        "gatenumber": "123",
        "carousel": "15",
        "exitnumber": "D",
        "remark": "도착",
        "airportCode": "KUL",
        "yoil": "화",
        "himidity": "79",
        "wind": "1.5",
        "temp": "28.0",
        "senstemp": "31.9",
        "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon02",
        "terminalid": "P02"
    },
    {
        "airline": null,
        "flightId": "OD820",
        "scheduleDateTime": "0600",
        "estimatedDateTime": "0608",
        "airport": "쿠알라룸푸르",
        "gatenumber": "20",
        "carousel": "6",
        "exitnumber": "B",
        "remark": "도착",
        "airportCode": "KUL",
        "yoil": "화",
        "himidity": "79",
        "wind": "1.5",
        "temp": "28.0",
        "senstemp": "31.9",
        "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon02",
        "terminalid": "P01"
    },
    {
        "airline": "로얄브루나이항공",
        "flightId": "BI651",
        "scheduleDateTime": "0650",
        "estimatedDateTime": "0610",
        "airport": "세리 베가완 브루나이",
        "gatenumber": "36",
        "carousel": "18",
        "exitnumber": "E",
        "remark": "도착",
        "airportCode": "BWN",
        "yoil": null,
        "himidity": null,
        "wind": null,
        "temp": null,
        "senstemp": null,
        "wimage": null,
        "terminalid": "P01"
    },
    {
        "airline": "에어프레미아",
        "flightId": "YP602",
        "scheduleDateTime": "0555",
        "estimatedDateTime": "0613",
        "airport": "방콕/수완나폼",
        "gatenumber": "39",
        "carousel": "22",
        "exitnumber": "E",
        "remark": "도착",
        "airportCode": "BKK",
        "yoil": "화",
        "himidity": "66",
        "wind": "2.6",
        "temp": "31.0",
        "senstemp": "36.5",
        "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon02",
        "terminalid": "P01"
    },
    {
        "airline": "라오항공",
        "flightId": "QV923",
        "scheduleDateTime": "0555",
        "estimatedDateTime": "0615",
        "airport": "비엔티안",
        "gatenumber": "50",
        "carousel": "19",
        "exitnumber": "E",
        "remark": "도착",
        "airportCode": "VTE",
        "yoil": "화",
        "himidity": "67",
        "wind": "1.0",
        "temp": "32.2",
        "senstemp": "39.8",
        "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon04",
        "terminalid": "P01"
    },
    {
        "airline": "대한항공",
        "flightId": "KE5764",
        "scheduleDateTime": "0630",
        "estimatedDateTime": "0614",
        "airport": "클라크필드",
        "gatenumber": "37",
        "carousel": "17",
        "exitnumber": "E",
        "remark": "도착",
        "airportCode": "CRK",
        "yoil": null,
        "himidity": null,
        "wind": null,
        "temp": null,
        "senstemp": null,
        "wimage": null,
        "terminalid": "P01"
    },
    {
        "airline": "진에어",
        "flightId": "LJ024",
        "scheduleDateTime": "0630",
        "estimatedDateTime": "0614",
        "airport": "클라크필드",
        "gatenumber": "37",
        "carousel": "17",
        "exitnumber": "E",
        "remark": "도착",
        "airportCode": "CRK",
        "yoil": null,
        "himidity": null,
        "wind": null,
        "temp": null,
        "senstemp": null,
        "wimage": null,
        "terminalid": "P01"
    },
    {
        "airline": "티웨이항공",
        "flightId": "TW104",
        "scheduleDateTime": "0620",
        "estimatedDateTime": "0621",
        "airport": "방콕/돈므앙",
        "gatenumber": "125",
        "carousel": "13",
        "exitnumber": "D",
        "remark": "도착",
        "airportCode": "DMK",
        "yoil": "화",
        "himidity": "66",
        "wind": "2.6",
        "temp": "31.0",
        "senstemp": "36.5",
        "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon02",
        "terminalid": "P02"
    },
    {
        "airline": "델타항공",
        "flightId": "DL7681",
        "scheduleDateTime": "0530",
        "estimatedDateTime": "0621",
        "airport": "다낭",
        "gatenumber": "261",
        "carousel": "7",
        "exitnumber": "B",
        "remark": "도착",
        "airportCode": "DAD",
        "yoil": null,
        "himidity": null,
        "wind": null,
        "temp": null,
        "senstemp": null,
        "wimage": null,
        "terminalid": "P03"
    },
    {
        "airline": "베트남항공",
        "flightId": "VN3440",
        "scheduleDateTime": "0530",
        "estimatedDateTime": "0621",
        "airport": "다낭",
        "gatenumber": "261",
        "carousel": "7",
        "exitnumber": "B",
        "remark": "도착",
        "airportCode": "DAD",
        "yoil": null,
        "himidity": null,
        "wind": null,
        "temp": null,
        "senstemp": null,
        "wimage": null,
        "terminalid": "P03"
    },
    {
        "airline": "버진 애트란틱항공",
        "flightId": "VS5522",
        "scheduleDateTime": "0530",
        "estimatedDateTime": "0621",
        "airport": "다낭",
        "gatenumber": "261",
        "carousel": "7",
        "exitnumber": "B",
        "remark": "도착",
        "airportCode": "DAD",
        "yoil": null,
        "himidity": null,
        "wind": null,
        "temp": null,
        "senstemp": null,
        "wimage": null,
        "terminalid": "P03"
    },
    {
        "airline": "대한항공",
        "flightId": "KE462",
        "scheduleDateTime": "0530",
        "estimatedDateTime": "0621",
        "airport": "다낭",
        "gatenumber": "261",
        "carousel": "7",
        "exitnumber": "B",
        "remark": "도착",
        "airportCode": "DAD",
        "yoil": null,
        "himidity": null,
        "wind": null,
        "temp": null,
        "senstemp": null,
        "wimage": null,
        "terminalid": "P03"
    },
    {
        "airline": "미얀마항공",
        "flightId": "UB8301",
        "scheduleDateTime": "0530",
        "estimatedDateTime": "0622",
        "airport": "양곤",
        "gatenumber": "38",
        "carousel": "18",
        "exitnumber": "E",
        "remark": "도착",
        "airportCode": "RGN",
        "yoil": "화",
        "himidity": "59",
        "wind": "1.0",
        "temp": "32.0",
        "senstemp": "36.8",
        "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon08",
        "terminalid": "P01"
    }
];
  

  return (

    <Container>
      <Title>오늘의 인천공항</Title>
      <AirplaneSVG></AirplaneSVG>

      <Wrapper>
        <form onSubmit={fromFlightApiJs.props.onSubmitFromView}>
          <label htmlFor="select">인천공항</label>
          <select id="select">
            <option value="ARRIVAL_URL">출발</option>
            <option value="DEPARTURE_URL">도착</option>
          </select>

          <input type="text" id="airport" list="airportsName" placeholder="공항을 입력하세요"/>
            <datalist id="airportsName">
              {airports.map((dat) => 
                <option key={dat.id} value={dat.airportName} />
              )}
            </datalist>

          <input type="text" id="airline" list="airlineCompanies" placeholder="항공사를 입력하세요"/>
            <datalist id="airlineCompanies">
              {airlines.map((dat) => 
                <option key={dat.codeICAO} value={dat.companyName} />
              )}
            </datalist>
          <button type="submit">확인</button>
        </form>
      </Wrapper>
            
      <Wrapper>
        <Conetent>
          <Pagination data={result} numOfItems={3} />
        </Conetent>
      </Wrapper>
      
      
    </Container>
      
  )
};
import { useState, useEffect } from "react";

import airlinesInfo from "../data/AirlinesInfo.json";
import { FlightApiView } from "../../view/pages/FlightApiView";
import { Pagination } from "../../action/CutOutItemsForPaging";


const findAirline = ( dataset, word ) => {
  let set = dataset;
  let len = set.length;
  let w = word;

  let result = null;

  for (let i = 0;i < len;) {
    if ( set[i].companyName === w ) {
      result = set[i].codeIATA;
      return result;
    }
    else i++;
  }
}

const findAirport = ( dataset, word ) => {
  let set = dataset;
  let len = set.length;
  let w = word;

  let result = null;

  for (let i = 0;i < len;) {
    if ( set[i].airportName === w ) {
      result = set[i].codeAirport;
      return result;
    }
    else i++;
  }
}

export const FlightApiJs = () => {
  const [data, setData] = useState();
  const [elements, setElements] = useState([]);


  const getReady = ( dat ) => {
    const result = dat;
    if (result === 'nothing') {
      setElements(<p>검색 결과가 존재하지 않습니다.</p>);
      return;
    } else {
      setElements(<Pagination data={result} display={5} interval={10} from={`flight`} />);
      return;
    }
  };

  const onSubmitFromView = (e) => {
    e.preventDefault();

    let len = e.target.length;
    let elements = Array.from(e.target);

    const result = [];

    let i=0;
    for (i;i<len-1;i++) {
      result.push(elements[i].value);
    }
    setData(result);
  };

  const callFlightApiData = async ( url, port, line ) => {
    
    const SERVICE_KEY = process.env.REACT_APP_INCHEON_INT_AIRPORT_WEATHER_INFO_API_KEY_A;
    
    const ARRIVAL_URL = `B551177/StatusOfPassengerWorldWeatherInfo/getPassengerArrivalsWorldWeather`;
    const DEPARTURE_URL = `B551177/StatusOfPassengerWorldWeatherInfo/getPassengerDeparturesWorldWeather`;
    
    let URL = '';
    const airport = (port === undefined) ? '' : port;
    const airline = (line === undefined) ? '' : line;

    if (url === 'ARRIVAL_URL') {
			URL = ARRIVAL_URL;
    }
    if (url === 'DEPARTURE_URL') {
      URL = DEPARTURE_URL;
    }
    

    const params = {
      'serviceKey': `${SERVICE_KEY}`,
      'numOfRows': '', 
      'pageNo': '1', 
      'from_time': '0000', 
      'to_time': '2400', 
      'airport': `${airport}`,
      'flight_id': '',
      'airline': `${airline}`,
      'lang':'K', 
      'type':'json'
    }

    const queryString = new URLSearchParams(params).toString()
  
    try {
      const response = await fetch(`/flight-api/arrival/${URL}?${queryString}`, {
        method: "GET",
      })

      if (!response.ok) {
				throw new Error('HTTP ERROR TO EXTERNAL API :: status ', response.status);
			}

      const result = await response.json();
      const finalData = result.response.body;

      const items = (finalData.items.length === 0) ? {items: 'nothing'} : finalData;
      let sendItems = items.items;

      getReady(sendItems);
      
    } catch (error) {
      console.error('CAN NOT CONNECT TO EXTERNAL API :: ', error);
      // local 테스트
      const forLocal55 = [
        {
          "airline": "비엣젯항공",
          "flightId": "VJ954T",
          "scheduleDateTime": "2355",
          "estimatedDateTime": "0000",
          "airport": "껀터 국제공항",
          "gatenumber": "114",
          "carousel": "8",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "VCA",
          "yoil": null,
          "himidity": null,
          "wind": null,
          "temp": null,
          "senstemp": null,
          "wimage": null,
          "terminalid": "P02"
      },
      {
          "airline": "중국국제항공",
          "flightId": "CA8881Y",
          "scheduleDateTime": "0005",
          "estimatedDateTime": "0012",
          "airport": "칭다오",
          "gatenumber": "12",
          "carousel": "2",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "TAO",
          "yoil": "수",
          "himidity": "89",
          "wind": "5.7",
          "temp": "27.0",
          "senstemp": "30.6",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon12",
          "terminalid": "P01"
      },
      {
          "airline": "아시아나항공",
          "flightId": "OZ6704Y",
          "scheduleDateTime": "0005",
          "estimatedDateTime": "0012",
          "airport": "칭다오",
          "gatenumber": "12",
          "carousel": "2",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "TAO",
          "yoil": "수",
          "himidity": "89",
          "wind": "5.7",
          "temp": "27.0",
          "senstemp": "30.6",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon12",
          "terminalid": "P01"
      },
      {
          "airline": "산동항공",
          "flightId": "SC4619Y",
          "scheduleDateTime": "0005",
          "estimatedDateTime": "0012",
          "airport": "칭다오",
          "gatenumber": "12",
          "carousel": "2",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "TAO",
          "yoil": "수",
          "himidity": "89",
          "wind": "5.7",
          "temp": "27.0",
          "senstemp": "30.6",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon12",
          "terminalid": "P01"
      },
      {
          "airline": "비엣젯항공",
          "flightId": "VJ978",
          "scheduleDateTime": "0030",
          "estimatedDateTime": "0033",
          "airport": "두옹 당(푸꿕)",
          "gatenumber": "110",
          "carousel": "7",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "PQC",
          "yoil": null,
          "himidity": null,
          "wind": null,
          "temp": null,
          "senstemp": null,
          "wimage": null,
          "terminalid": "P02"
      },
      {
          "airline": "대한항공",
          "flightId": "KE5650",
          "scheduleDateTime": "0025",
          "estimatedDateTime": "0048",
          "airport": "울란바트로",
          "gatenumber": "14",
          "carousel": "5",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "UBN",
          "yoil": null,
          "himidity": null,
          "wind": null,
          "temp": null,
          "senstemp": null,
          "wimage": null,
          "terminalid": "P01"
      },
      {
          "airline": "몽골항공",
          "flightId": "OM307",
          "scheduleDateTime": "0025",
          "estimatedDateTime": "0048",
          "airport": "울란바트로",
          "gatenumber": "14",
          "carousel": "5",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "UBN",
          "yoil": null,
          "himidity": null,
          "wind": null,
          "temp": null,
          "senstemp": null,
          "wimage": null,
          "terminalid": "P01"
      },
      {
          "airline": "타이거에어 타이완",
          "flightId": "IT600",
          "scheduleDateTime": "0130",
          "estimatedDateTime": "0121",
          "airport": "타이베이",
          "gatenumber": "112",
          "carousel": "7",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "TPE",
          "yoil": "수",
          "himidity": "63",
          "wind": "3.1",
          "temp": "33.0",
          "senstemp": "40.6",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon03",
          "terminalid": "P02"
      },
      {
          "airline": "세부퍼시픽항공",
          "flightId": "5J188Y",
          "scheduleDateTime": "0210",
          "estimatedDateTime": "0227",
          "airport": "마닐라",
          "gatenumber": "106",
          "carousel": "9",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "MNL",
          "yoil": "수",
          "himidity": "94",
          "wind": "5.1",
          "temp": "28.0",
          "senstemp": "34.5",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon11",
          "terminalid": "P02"
      },
      {
          "airline": "코파항공",
          "flightId": "CM8003",
          "scheduleDateTime": "0420",
          "estimatedDateTime": "0341",
          "airport": "로스앤젤레스",
          "gatenumber": "8",
          "carousel": "4",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "LAX",
          "yoil": "수",
          "himidity": "83",
          "wind": "0.0",
          "temp": "16.7",
          "senstemp": "16.7",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon01",
          "terminalid": "P01"
      },
      {
          "airline": "싱가포르항공",
          "flightId": "SQ5703",
          "scheduleDateTime": "0420",
          "estimatedDateTime": "0341",
          "airport": "로스앤젤레스",
          "gatenumber": "8",
          "carousel": "4",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "LAX",
          "yoil": "수",
          "himidity": "83",
          "wind": "0.0",
          "temp": "16.7",
          "senstemp": "16.7",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon01",
          "terminalid": "P01"
      },
      {
          "airline": "타이항공",
          "flightId": "TG6742",
          "scheduleDateTime": "0420",
          "estimatedDateTime": "0341",
          "airport": "로스앤젤레스",
          "gatenumber": "8",
          "carousel": "4",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "LAX",
          "yoil": "수",
          "himidity": "83",
          "wind": "0.0",
          "temp": "16.7",
          "senstemp": "16.7",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon01",
          "terminalid": "P01"
      },
      {
          "airline": "아시아나항공",
          "flightId": "OZ203",
          "scheduleDateTime": "0420",
          "estimatedDateTime": "0341",
          "airport": "로스앤젤레스",
          "gatenumber": "8",
          "carousel": "4",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "LAX",
          "yoil": "수",
          "himidity": "83",
          "wind": "0.0",
          "temp": "16.7",
          "senstemp": "16.7",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon01",
          "terminalid": "P01"
      },
      {
          "airline": "아시아나항공",
          "flightId": "OZ6621",
          "scheduleDateTime": "0420",
          "estimatedDateTime": "0413",
          "airport": "샌프란시스코",
          "gatenumber": "24",
          "carousel": "3",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "SFO",
          "yoil": "수",
          "himidity": "83",
          "wind": "4.1",
          "temp": "12.8",
          "senstemp": "11.4",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon04",
          "terminalid": "P01"
      },
      {
          "airline": "유나이티드항공",
          "flightId": "UA805",
          "scheduleDateTime": "0420",
          "estimatedDateTime": "0413",
          "airport": "샌프란시스코",
          "gatenumber": "24",
          "carousel": "3",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "SFO",
          "yoil": "수",
          "himidity": "83",
          "wind": "4.1",
          "temp": "12.8",
          "senstemp": "11.4",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon04",
          "terminalid": "P01"
      },
      {
          "airline": "싱가포르항공",
          "flightId": "SQ5711",
          "scheduleDateTime": "0430",
          "estimatedDateTime": "0417",
          "airport": "샌프란시스코",
          "gatenumber": "22",
          "carousel": "5",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "SFO",
          "yoil": "수",
          "himidity": "83",
          "wind": "4.1",
          "temp": "12.8",
          "senstemp": "11.4",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon04",
          "terminalid": "P01"
      },
      {
          "airline": "타이항공",
          "flightId": "TG6744",
          "scheduleDateTime": "0430",
          "estimatedDateTime": "0417",
          "airport": "샌프란시스코",
          "gatenumber": "22",
          "carousel": "5",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "SFO",
          "yoil": "수",
          "himidity": "83",
          "wind": "4.1",
          "temp": "12.8",
          "senstemp": "11.4",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon04",
          "terminalid": "P01"
      },
      {
          "airline": "아시아나항공",
          "flightId": "OZ211",
          "scheduleDateTime": "0430",
          "estimatedDateTime": "0417",
          "airport": "샌프란시스코",
          "gatenumber": "22",
          "carousel": "5",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "SFO",
          "yoil": "수",
          "himidity": "83",
          "wind": "4.1",
          "temp": "12.8",
          "senstemp": "11.4",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon04",
          "terminalid": "P01"
      },
      {
          "airline": "대한항공",
          "flightId": "KE5680",
          "scheduleDateTime": "0430",
          "estimatedDateTime": "0419",
          "airport": "나트랑",
          "gatenumber": "103",
          "carousel": "8",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "CXR",
          "yoil": null,
          "himidity": null,
          "wind": null,
          "temp": null,
          "senstemp": null,
          "wimage": null,
          "terminalid": "P02"
      },
      {
          "airline": "베트남항공",
          "flightId": "VN440",
          "scheduleDateTime": "0430",
          "estimatedDateTime": "0419",
          "airport": "나트랑",
          "gatenumber": "103",
          "carousel": "8",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "CXR",
          "yoil": null,
          "himidity": null,
          "wind": null,
          "temp": null,
          "senstemp": null,
          "wimage": null,
          "terminalid": "P02"
      },
      {
          "airline": "일본항공",
          "flightId": "JL5257",
          "scheduleDateTime": "0435",
          "estimatedDateTime": "0424",
          "airport": "도쿄/하네다",
          "gatenumber": "245",
          "carousel": "3",
          "exitnumber": "A",
          "remark": "도착",
          "airportCode": "HND",
          "yoil": "수",
          "himidity": "84",
          "wind": "7.2",
          "temp": "27.0",
          "senstemp": "30.1",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon03",
          "terminalid": "P03"
      },
      {
          "airline": "버진 애트란틱항공",
          "flightId": "VS5530",
          "scheduleDateTime": "0435",
          "estimatedDateTime": "0424",
          "airport": "도쿄/하네다",
          "gatenumber": "245",
          "carousel": "3",
          "exitnumber": "A",
          "remark": "도착",
          "airportCode": "HND",
          "yoil": "수",
          "himidity": "84",
          "wind": "7.2",
          "temp": "27.0",
          "senstemp": "30.1",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon03",
          "terminalid": "P03"
      },
      {
          "airline": "에어 프랑스",
          "flightId": "AF5382",
          "scheduleDateTime": "0435",
          "estimatedDateTime": "0424",
          "airport": "도쿄/하네다",
          "gatenumber": "245",
          "carousel": "3",
          "exitnumber": "A",
          "remark": "도착",
          "airportCode": "HND",
          "yoil": "수",
          "himidity": "84",
          "wind": "7.2",
          "temp": "27.0",
          "senstemp": "30.1",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon03",
          "terminalid": "P03"
      },
      {
          "airline": "대한항공",
          "flightId": "KE720",
          "scheduleDateTime": "0435",
          "estimatedDateTime": "0424",
          "airport": "도쿄/하네다",
          "gatenumber": "245",
          "carousel": "3",
          "exitnumber": "A",
          "remark": "도착",
          "airportCode": "HND",
          "yoil": "수",
          "himidity": "84",
          "wind": "7.2",
          "temp": "27.0",
          "senstemp": "30.1",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon03",
          "terminalid": "P03"
      },
      {
          "airline": "피치항공",
          "flightId": "MM809",
          "scheduleDateTime": "0440",
          "estimatedDateTime": "0437",
          "airport": "도쿄/하네다",
          "gatenumber": "114",
          "carousel": "9",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "HND",
          "yoil": "수",
          "himidity": "84",
          "wind": "7.2",
          "temp": "27.0",
          "senstemp": "30.1",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon03",
          "terminalid": "P02"
      },
      {
          "airline": "아에로멕시코",
          "flightId": "AM6701",
          "scheduleDateTime": "0450",
          "estimatedDateTime": "0444",
          "airport": "로스앤젤레스",
          "gatenumber": "233",
          "carousel": "5",
          "exitnumber": "A",
          "remark": "도착",
          "airportCode": "LAX",
          "yoil": "수",
          "himidity": "83",
          "wind": "0.0",
          "temp": "16.7",
          "senstemp": "16.7",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon01",
          "terminalid": "P03"
      },
      {
          "airline": "델타항공",
          "flightId": "DL9043",
          "scheduleDateTime": "0450",
          "estimatedDateTime": "0444",
          "airport": "로스앤젤레스",
          "gatenumber": "233",
          "carousel": "5",
          "exitnumber": "A",
          "remark": "도착",
          "airportCode": "LAX",
          "yoil": "수",
          "himidity": "83",
          "wind": "0.0",
          "temp": "16.7",
          "senstemp": "16.7",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon01",
          "terminalid": "P03"
      },
      {
          "airline": "란항공",
          "flightId": "LA8425",
          "scheduleDateTime": "0450",
          "estimatedDateTime": "0444",
          "airport": "로스앤젤레스",
          "gatenumber": "233",
          "carousel": "5",
          "exitnumber": "A",
          "remark": "도착",
          "airportCode": "LAX",
          "yoil": "수",
          "himidity": "83",
          "wind": "0.0",
          "temp": "16.7",
          "senstemp": "16.7",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon01",
          "terminalid": "P03"
      },
      {
          "airline": "대한항공",
          "flightId": "KE012",
          "scheduleDateTime": "0450",
          "estimatedDateTime": "0444",
          "airport": "로스앤젤레스",
          "gatenumber": "233",
          "carousel": "5",
          "exitnumber": "A",
          "remark": "도착",
          "airportCode": "LAX",
          "yoil": "수",
          "himidity": "83",
          "wind": "0.0",
          "temp": "16.7",
          "senstemp": "16.7",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon01",
          "terminalid": "P03"
      },
      {
          "airline": "델타항공",
          "flightId": "DL7858",
          "scheduleDateTime": "0505",
          "estimatedDateTime": "0447",
          "airport": "방콕/수완나폼",
          "gatenumber": "234",
          "carousel": "2",
          "exitnumber": "A",
          "remark": "도착",
          "airportCode": "BKK",
          "yoil": "수",
          "himidity": "59",
          "wind": "4.6",
          "temp": "33.0",
          "senstemp": "39.2",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon02",
          "terminalid": "P03"
      },
      {
          "airline": "대한항공",
          "flightId": "KE658",
          "scheduleDateTime": "0505",
          "estimatedDateTime": "0447",
          "airport": "방콕/수완나폼",
          "gatenumber": "234",
          "carousel": "2",
          "exitnumber": "A",
          "remark": "도착",
          "airportCode": "BKK",
          "yoil": "수",
          "himidity": "59",
          "wind": "4.6",
          "temp": "33.0",
          "senstemp": "39.2",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon02",
          "terminalid": "P03"
      },
      {
          "airline": "비엣젯항공",
          "flightId": "VJ836",
          "scheduleDateTime": "0430",
          "estimatedDateTime": "0447",
          "airport": "나트랑",
          "gatenumber": "105",
          "carousel": "10",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "CXR",
          "yoil": null,
          "himidity": null,
          "wind": null,
          "temp": null,
          "senstemp": null,
          "wimage": null,
          "terminalid": "P02"
      },
      {
          "airline": "대한항공",
          "flightId": "KE5762",
          "scheduleDateTime": "0510",
          "estimatedDateTime": "0452",
          "airport": "코타키나발루",
          "gatenumber": "45",
          "carousel": "17",
          "exitnumber": "E",
          "remark": "도착",
          "airportCode": "BKI",
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
          "flightId": "LJ062",
          "scheduleDateTime": "0510",
          "estimatedDateTime": "0452",
          "airport": "코타키나발루",
          "gatenumber": "45",
          "carousel": "17",
          "exitnumber": "E",
          "remark": "도착",
          "airportCode": "BKI",
          "yoil": null,
          "himidity": null,
          "wind": null,
          "temp": null,
          "senstemp": null,
          "wimage": null,
          "terminalid": "P01"
      },
      {
          "airline": "대한항공",
          "flightId": "KE006",
          "scheduleDateTime": "0450",
          "estimatedDateTime": "0459",
          "airport": "라스베이거스",
          "gatenumber": "247",
          "carousel": "4",
          "exitnumber": "A",
          "remark": "도착",
          "airportCode": "LAS",
          "yoil": null,
          "himidity": null,
          "wind": null,
          "temp": null,
          "senstemp": null,
          "wimage": null,
          "terminalid": "P03"
      },
      {
          "airline": "델타항공",
          "flightId": "DL9035",
          "scheduleDateTime": "0450",
          "estimatedDateTime": "0459",
          "airport": "라스베이거스",
          "gatenumber": "247",
          "carousel": "4",
          "exitnumber": "A",
          "remark": "도착",
          "airportCode": "LAS",
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
          "flightId": "KE696",
          "scheduleDateTime": "0515",
          "estimatedDateTime": "0505",
          "airport": "카트만두",
          "gatenumber": "235",
          "carousel": "1",
          "exitnumber": "A",
          "remark": "도착",
          "airportCode": "KTM",
          "yoil": "수",
          "himidity": "100",
          "wind": "1.0",
          "temp": "26.7",
          "senstemp": "30.9",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon05",
          "terminalid": "P03"
      },
      {
          "airline": "버진 애트란틱항공",
          "flightId": "VS5516",
          "scheduleDateTime": "0525",
          "estimatedDateTime": "0508",
          "airport": "홍콩",
          "gatenumber": "258",
          "carousel": "8",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "HKG",
          "yoil": "수",
          "himidity": "71",
          "wind": "3.6",
          "temp": "32.0",
          "senstemp": "40.6",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon02",
          "terminalid": "P03"
      },
      {
          "airline": "델타항공",
          "flightId": "DL7916",
          "scheduleDateTime": "0525",
          "estimatedDateTime": "0508",
          "airport": "홍콩",
          "gatenumber": "258",
          "carousel": "8",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "HKG",
          "yoil": "수",
          "himidity": "71",
          "wind": "3.6",
          "temp": "32.0",
          "senstemp": "40.6",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon02",
          "terminalid": "P03"
      },
      {
          "airline": "에티하드 항공",
          "flightId": "EY8495",
          "scheduleDateTime": "0525",
          "estimatedDateTime": "0508",
          "airport": "홍콩",
          "gatenumber": "258",
          "carousel": "8",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "HKG",
          "yoil": "수",
          "himidity": "71",
          "wind": "3.6",
          "temp": "32.0",
          "senstemp": "40.6",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon02",
          "terminalid": "P03"
      },
      {
          "airline": "대한항공",
          "flightId": "KE178",
          "scheduleDateTime": "0525",
          "estimatedDateTime": "0508",
          "airport": "홍콩",
          "gatenumber": "258",
          "carousel": "8",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "HKG",
          "yoil": "수",
          "himidity": "71",
          "wind": "3.6",
          "temp": "32.0",
          "senstemp": "40.6",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon02",
          "terminalid": "P03"
      },
      {
          "airline": "대한항공",
          "flightId": "KE5036",
          "scheduleDateTime": "0515",
          "estimatedDateTime": "0513",
          "airport": "애틀랜타",
          "gatenumber": "251",
          "carousel": "7",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "ATL",
          "yoil": null,
          "himidity": null,
          "wind": null,
          "temp": null,
          "senstemp": null,
          "wimage": null,
          "terminalid": "P03"
      },
      {
          "airline": "델타항공",
          "flightId": "DL027",
          "scheduleDateTime": "0515",
          "estimatedDateTime": "0513",
          "airport": "애틀랜타",
          "gatenumber": "251",
          "carousel": "7",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "ATL",
          "yoil": null,
          "himidity": null,
          "wind": null,
          "temp": null,
          "senstemp": null,
          "wimage": null,
          "terminalid": "P03"
      },
      {
          "airline": "제주항공",
          "flightId": "7C4468",
          "scheduleDateTime": "0530",
          "estimatedDateTime": "0518",
          "airport": "보홀 팡라오",
          "gatenumber": "110",
          "carousel": "11",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "TAG",
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
          "flightId": "VJ880",
          "scheduleDateTime": "0500",
          "estimatedDateTime": "0521",
          "airport": "다낭",
          "gatenumber": "106",
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
          "terminalid": "P02"
      },
      {
          "airline": "홍콩항공",
          "flightId": "HX1566",
          "scheduleDateTime": "0510",
          "estimatedDateTime": "0524",
          "airport": "홍콩",
          "gatenumber": "14",
          "carousel": "6",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "HKG",
          "yoil": "수",
          "himidity": "71",
          "wind": "3.6",
          "temp": "32.0",
          "senstemp": "40.6",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon02",
          "terminalid": "P01"
      },
      {
          "airline": "유나이티드항공",
          "flightId": "UA7307",
          "scheduleDateTime": "0510",
          "estimatedDateTime": "0524",
          "airport": "홍콩",
          "gatenumber": "14",
          "carousel": "6",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "HKG",
          "yoil": "수",
          "himidity": "71",
          "wind": "3.6",
          "temp": "32.0",
          "senstemp": "40.6",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon02",
          "terminalid": "P01"
      },
      {
          "airline": "아시아나항공",
          "flightId": "OZ746",
          "scheduleDateTime": "0510",
          "estimatedDateTime": "0524",
          "airport": "홍콩",
          "gatenumber": "14",
          "carousel": "6",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "HKG",
          "yoil": "수",
          "himidity": "71",
          "wind": "3.6",
          "temp": "32.0",
          "senstemp": "40.6",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon02",
          "terminalid": "P01"
      },
      {
          "airline": "미얀마항공",
          "flightId": "UB8301",
          "scheduleDateTime": "0530",
          "estimatedDateTime": "0530",
          "airport": "양곤",
          "gatenumber": "",
          "carousel": "",
          "exitnumber": "",
          "remark": "결항",
          "airportCode": "RGN",
          "yoil": "수",
          "himidity": "50",
          "wind": "1.0",
          "temp": "35.0",
          "senstemp": "40.6",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon02",
          "terminalid": "P01"
      },
      {
          "airline": "델타항공",
          "flightId": "DL7910",
          "scheduleDateTime": "0525",
          "estimatedDateTime": "0534",
          "airport": "하노이",
          "gatenumber": "261",
          "carousel": "10",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "HAN",
          "yoil": "수",
          "himidity": "75",
          "wind": "1.5",
          "temp": "32.3",
          "senstemp": "43.1",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon11",
          "terminalid": "P03"
      },
      {
          "airline": "베트남항공",
          "flightId": "VN3410",
          "scheduleDateTime": "0525",
          "estimatedDateTime": "0534",
          "airport": "하노이",
          "gatenumber": "261",
          "carousel": "10",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "HAN",
          "yoil": "수",
          "himidity": "75",
          "wind": "1.5",
          "temp": "32.3",
          "senstemp": "43.1",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon11",
          "terminalid": "P03"
      },
      {
          "airline": "버진 애트란틱항공",
          "flightId": "VS5518",
          "scheduleDateTime": "0525",
          "estimatedDateTime": "0534",
          "airport": "하노이",
          "gatenumber": "261",
          "carousel": "10",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "HAN",
          "yoil": "수",
          "himidity": "75",
          "wind": "1.5",
          "temp": "32.3",
          "senstemp": "43.1",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon11",
          "terminalid": "P03"
      },
      {
          "airline": "대한항공",
          "flightId": "KE456",
          "scheduleDateTime": "0525",
          "estimatedDateTime": "0534",
          "airport": "하노이",
          "gatenumber": "261",
          "carousel": "10",
          "exitnumber": "B",
          "remark": "도착",
          "airportCode": "HAN",
          "yoil": "수",
          "himidity": "75",
          "wind": "1.5",
          "temp": "32.3",
          "senstemp": "43.1",
          "wimage": "https://odp.airport.kr/apiPortal/weather_icon/icon11",
          "terminalid": "P03"
      },
      {
          "airline": "대한항공",
          "flightId": "KE462",
          "scheduleDateTime": "0530",
          "estimatedDateTime": "0533",
          "airport": "다낭",
          "gatenumber": "241",
          "carousel": "3",
          "exitnumber": "A",
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
          "airline": "델타항공",
          "flightId": "DL7681",
          "scheduleDateTime": "0530",
          "estimatedDateTime": "0533",
          "airport": "다낭",
          "gatenumber": "241",
          "carousel": "3",
          "exitnumber": "A",
          "remark": "도착",
          "airportCode": "DAD",
          "yoil": null,
          "himidity": null,
          "wind": null,
          "temp": null,
          "senstemp": null,
          "wimage": null,
          "terminalid": "P03"
      }
      ];
      getReady(forLocal55);
    }
  };
  
  useEffect(() => {
    const airports = airlinesInfo.airport;
    const airlines = airlinesInfo.airline;
    
    if ( !(data === undefined) ) {
      const url = data[0];
      const port = findAirport(airports, data[1]);
      const line = findAirline(airlines, data[2]);

      callFlightApiData( url, port, line );
    }
  }, [data]);

  
  const toFlightApiViewProps = {
    onSubmitFromView,
    elements,
  }
  console.log('api is working', elements);

  return (
    <>
      <FlightApiView props={ { ...toFlightApiViewProps } }/>
    </>
  )
}
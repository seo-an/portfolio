import { useState, useMemo } from "react";

import AIRLINES_INFO from "../data/airlines_info.json";

import { requestDataFromFlightApi as callApiData } from "../../action/requestDataFromFlightApi";
import { findAirline, findAirport } from "../../action/actionsForFlightApi";

import FlightApiSearchForm from "../../view/pages/FlightApiSearchForm";
import FlightApiResultDisplay from "../../view/pages/FlightApiResultDisplay.js";



export const FlightApiJs = () => {
	const [airports, setAirports] = useState(AIRLINES_INFO.airport);
	const [airlines, setAirlines] = useState(AIRLINES_INFO.airline);

  const [searchObj, setSearchObj] = useState();
  const [elements, setElements] = useState([]);

	const pageSize = 5;
	const paginationSize = 5;


	const onSubmitFromView = (e) => {
    e.preventDefault();

    let len = e.target.length;
    let test = Array.from(e.target);

    const result = [];

    let i=0;
    for (i;i<len-1;i++) {
      result.push(test[i].value);
    }
		console.log('rrr', result);
		return setSearchObj(result);
  };


	const setPageView = ( dat ) => {
    const raw = dat;
		const len = raw.length;

    if (raw === 'nothing')  {
			console.error('비었음');
			setElements('nothing');
			return;
		};

		const cooking = [];
		let today = new Date();

		for (let i = 1; i < len + 1; i++) {
			cooking.push( (raw[i-1]) ? (<div className="flight" key={`item+${i}+${today.getTime()}`}>
				<ul>
					<li>항공편: {raw[i-1].flightId}</li>
					<li>상태: {(raw[i-1].remark) ? raw[i-1].remark : '확인되지 않음'}</li> 
					<li>습도: {(raw[i-1].himidity)? `${raw[i-1].himidity}%` : '확인되지 않음'}</li>
					<li>풍속: {(raw[i-1].wind)? `${raw[i-1].wind}㎧` : '확인되지 않음'}</li>
					<li>관측 기온: {(raw[i-1].temp)? `${raw[i-1].temp}℃` : '확인되지 않음'}</li>
					<li>항공사: {raw[i-1].airline}</li>
					<li>공항: {raw[i-1].airport}</li>
				</ul>
			</div>) : null );
		}

		// raw data 넘기기
		setElements(cooking);
		return;
  };


	useMemo(() => {
    // const airports = AIRLINES_INFO.airport;
    // const airlines = AIRLINES_INFO.airline;
    
    if ( !(searchObj === undefined) ) {
      const url = searchObj[0];
      const port = findAirport(airports, searchObj[1]);
      const line = findAirline(airlines, searchObj[2]);

			callApiData( url, port, line ).then((res) => {setPageView(res)});
    }

  }, [airports, airlines, searchObj]);


	const goPagination = {
		data: elements,
		pageSize: pageSize,
		paginationSize: paginationSize
	};


  return (
    <>
			<FlightApiSearchForm props={ onSubmitFromView } />
			<FlightApiResultDisplay props={ { ...goPagination } }/>
    </>
  )
}
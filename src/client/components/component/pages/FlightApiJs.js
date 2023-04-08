import { useState, useEffect } from "react";
import axios from "axios";
import styled from "styled-components";

import { FlightApiView } from "../../view/pages/FlightApiView";





// // 공공 API 실습중
// // https://okky.kr/articles/766435


const callAirport = () => {

  const fetchApi = async () => {
    const SERVICE_KEY = process.env.REACT_APP_INCHEON_INT_AIRPORT_WEATHER_INFO_API_KEY;
    const ARRIVAL_URL = `/B551177/StatusOfPassengerWorldWeatherInfo/getPassengerArrivalsWorldWeather`;
    const DEPARTURE_URL = `/B551177/StatusOfPassengerWorldWeatherInfo/getPassengerDeparturesWorldWeather`;
  
    // proxy 통하니까 decoding service key 넣어야 작동했음
    const getApi = await axios({
      method: "GET",
      url: `/weather-api${ARRIVAL_URL}`,
      params: {
        'serviceKey': `${SERVICE_KEY}`,
        'numOfRows': '10', 
        'pageNo': '1', 
        'from_time': '0000', 
        'to_time': '2400', 
        'airport': '',
        'flight_id': '',
        'airline': '',
        'lang':'K', 
        'type':'json'
      },
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 60000,
    })
    .then(response => response.data.response.body)
    .then(data => console.log(data))
    .catch((error) => {
      console.log('! ERROR FAIL TO CONNECT TO fetchApi :: ', error);
    });
  };

  fetchApi();
}




  // return (
  //   <div>
  //     <button onClick={handleTranslate}>Translate</button>
  //     <p>{result}</p>
  //   </div>
  // );
  // return handleTranslate();

// console.log(hangulCode.indexOf(val));
// indexOf();
// charCodeAt(0);

export const FlightApiJs = () => {
  callAirport();

  const search = (e) => {
    // const word = [];
    // console.log('handle change', e.target.value);
    // const nowTyping = e.target.value.charCodeAt(0);

    // word.push(nowTyping);
    // console.log(word);

    const bb = e.target.value;
    return bb;
  };

  const real = () => {

  }

  const onSubmit = (e) => {
    e.preventDefault();
  };

  
  // const air1 = document.querySelector("input#airlines").value;
  // console.log(hangulCode.indexOf(air1));

  return (
    <>
      <FlightApiView props={ 'a' }/>
      <div>
        <form onSubmit={onSubmit}>
          <input name="test" id="airlines" placeholder="항공사" onChange={search}></input>
        </form>
      </div>
    </>
  )
}
import { useState, useEffect, useCallback } from "react";
import axios from "axios";
import styled from "styled-components";

import { FlightApiView } from "../../view/pages/FlightApiView";


const findAirline = ( dataset, word ) => {
  let set = dataset;
  let len = set.length;
  let w = word;

  let result = null;

  let i = 0;
  for (i;i<len;) {
    if ( set[i].companyName === w ) return result = set[i].codeIATA;
    else i++;
  }
}

const findAirport = ( dataset, word ) => {
  let set = dataset;
  let len = set.length;
  let w = word;

  let result = null;

  let i = 0;
  for (i;i<len;) {
    if ( set[i].airportName === w ) return result = set[i].codeAirport;
    else i++;
  }
}


// const callFlightApiData = async ( url, port, line ) => {

//   // const fetchApi = async ( data ) => {

//   const SERVICE_KEY = process.env.REACT_APP_INCHEON_INT_AIRPORT_WEATHER_INFO_API_KEY;
//   const ARRIVAL_URL = `/B551177/StatusOfPassengerWorldWeatherInfo/getPassengerArrivalsWorldWeather`;
//   const DEPARTURE_URL = `/B551177/StatusOfPassengerWorldWeatherInfo/getPassengerDeparturesWorldWeather`;

//   const URL = (url) ? ARRIVAL_URL : DEPARTURE_URL;
//   const airport = (port === undefined) ? '' : port;
//   const airline = (line === undefined) ? '' : line; 

//   // proxy 통하니까 decoding service key 넣어야 작동했음
//   const getApi = await axios({
//     method: "GET",
//     url: `/weather-api${URL}`,
//     params: {
//       'serviceKey': `${SERVICE_KEY}`,
//       'numOfRows': '20', 
//       'pageNo': '1', 
//       'from_time': '0000', 
//       'to_time': '2400', 
//       'airport': `${airport}`,
//       'flight_id': '',
//       'airline': `${airline}`,
//       'lang':'K', 
//       'type':'json'
//     },
//     headers: {
//       'Content-Type': 'application/json',
//     },
//     timeout: 60000,
//   })
//   .then(response => response.data.response.body)
//   .then(data => data)
//   .catch((error) => {
//     console.log('! ERROR FAIL TO CONNECT TO fetchApi :: ', error);
//   });
// };

  // fetchApi();
// }


export const FlightApiJs = () => {
  
  const [data, setData] = useState();
  const [final, setFinal] = useState();
  let jsonData = null;

  const getFlightApiData = (data) => {
    return jsonData = data;
  }

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

    // const fetchApi = async ( data ) => {
  
    const SERVICE_KEY = process.env.REACT_APP_INCHEON_INT_AIRPORT_WEATHER_INFO_API_KEY_A;
    const ARRIVAL_URL = `B551177/StatusOfPassengerWorldWeatherInfo/getPassengerArrivalsWorldWeather`;
    const DEPARTURE_URL = `B551177/StatusOfPassengerWorldWeatherInfo/getPassengerDeparturesWorldWeather`;
  
    const URL = (url) ? ARRIVAL_URL : DEPARTURE_URL;
    const airport = (port === undefined) ? '' : port;
    const airline = (line === undefined) ? '' : line; 
  
    // proxy 통하니까 decoding service key 넣어야 작동했음
    const getApi = await axios({
      method: "GET",
      url: `/flight-api/arrival/${ARRIVAL_URL}`,
      params: {
        'serviceKey': `${SERVICE_KEY}`,
        'numOfRows': '20', 
        'pageNo': '1', 
        'from_time': '0000', 
        'to_time': '2400', 
        'airport': `${airport}`,
        'flight_id': '',
        'airline': `${airline}`,
        'lang':'K', 
        'type':'json'
      },
      headers: {
        'Content-Type': 'application/json',
      },
      timeout: 60000,
    })
    .then(response => response.data.response.body)
    .then(data => setFinal(data))
    .catch((error) => {
      console.log('! ERROR FAIL TO CONNECT TO fetchApi :: ', error);
    });
  };

  
  useEffect(() => {
    const airlines = jsonData.airline;
    const airports = jsonData.airport;

    if ( !(data === undefined) ) {
      const url = data[0];
      const port = findAirport(airports, data[1]);
      const line = findAirline(airlines, data[2]);

      callFlightApiData( url, port, line );
    }
  }, [data, jsonData])

  

  const toFlightApiViewProps = {
    onSubmitFromView,
    getFlightApiData,
    final
  }


  return (
    <>
      <FlightApiView props={ { ...toFlightApiViewProps } }/>
      {/* <div>
        <form onSubmit={onSubmit}>
          <input name="test" id="airlines" placeholder="항공사" onChange={catchTyping}></input>
        </form>
      </div> */}
    </>
  )
}
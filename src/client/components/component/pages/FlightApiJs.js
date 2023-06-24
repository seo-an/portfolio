import { useState, useEffect } from "react";
// import axios from "axios";

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
    const SERVICE_KEY = process.env.REACT_APP_INCHEON_INT_AIRPORT_WEATHER_INFO_API_KEY_A;
    const ARRIVAL_URL = `B551177/StatusOfPassengerWorldWeatherInfo/getPassengerArrivalsWorldWeather`;
    // const DEPARTURE_URL = `B551177/StatusOfPassengerWorldWeatherInfo/getPassengerDeparturesWorldWeather`;
  
    // const URL = (url) ? ARRIVAL_URL : DEPARTURE_URL;
    const airport = (port === undefined) ? '' : port;
    const airline = (line === undefined) ? '' : line;

    const params = {
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
    }

    const queryString = new URLSearchParams(params).toString()
  
    try {
      const response = await fetch(`/flight-api/arrival/${ARRIVAL_URL}?${queryString}`, {
        method: "GET",
      })

      if (!response.ok) {
				throw new Error('HTTP ERROR TO EXTERNAL API :: status ', response.status);
			}

      const result = await response.json();
      const finalData = result.response.body;

      setFinal(finalData);

    } catch (error) {
      console.error('CAN NOT CONNECT TO EXTERNAL API :: ', error);
    }
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
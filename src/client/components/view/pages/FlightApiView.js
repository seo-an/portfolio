import styled from "styled-components";
// import { useEffect } from "react";

import { ReactComponent as AirplaneSVG } from "../icon/svg/airplane.svg";
import airlinesInfo from "../../data/AirlinesInfo.json"


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
  // console.log(fromFlightApiJs.props.catchTyping);
	// console.log('in viewer', props.props.body.items);
	// const apiData = props.props.body.items;
	// console.log(apiData);

  const airlines = airlinesInfo.airline;
  const airports = airlinesInfo.airport;

  fromFlightApiJs.props.getFlightApiData(airlinesInfo);
  
  const finalData = (fromFlightApiJs.props.final === undefined) ? {items: []} : fromFlightApiJs.props.final;
  let result = finalData.items;
  console.log(result);

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
          {result.map((dat) => 
            <ul key={dat.index}>
              <li>항공사: {dat.airline}</li>
              <li>공항: {dat.airport}</li>
              <li>상태: {dat.remark}</li>
            </ul>
          )}
        </Conetent>
      </Wrapper>
      
    </Container>
      
  )
};
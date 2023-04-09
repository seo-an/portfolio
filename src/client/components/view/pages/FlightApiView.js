import styled from "styled-components";

import { ReactComponent as AirplaneSVG } from "../icon/svg/airplane.svg";
import airlinesInfo from "../../data/airlinesInfo.json"


export const Wrapper = styled.div `
  display: flex;
  margin: 8px 16px;
`

export const FlightApiView = ( fromFlightApiJs ) => {
  // console.log(fromFlightApiJs.props.catchTyping);
	// console.log('in viewer', props.props.body.items);
	// const apiData = props.props.body.items;
	// console.log(apiData);

  
  console.log(airlinesInfo);
  return (

			<Wrapper>
        <h1>오늘의 인천공항</h1>
        {/* {apiData.map((item) => (<div key={item.flightId}>{item.airline}</div>))} */}
        <AirplaneSVG></AirplaneSVG>

        <div>
        <form onSubmit={fromFlightApiJs.props.onSubmit}>
          {/* <input name="test" id="123" list="browsers" placeholder="항공사" onChange={fromFlightApiJs.props.catchTyping}></input> */}
          
        </form>
        <input type="text" list="browsers" />
          <datalist id="browsers">
            <option value="Internet Explorer" />
            <option value="Firefox" />
            <option value="Chrome" />
            <option value="Opera" />
            <option value="Safari" />
          </datalist>
      </div>
      </Wrapper>
      

  )
};
import styled from "styled-components";

import { ReactComponent as AirplaneSVG } from "../icon/svg/airplane.svg";


export const Wrapper = styled.div `
  display: flex;
  margin: 8px 16px;
`

export const FlightApiView = ( props ) => {
	// console.log('in viewer', props.props.body.items);
	// const apiData = props.props.body.items;
	// console.log(apiData);
  return (
    <>
			<Wrapper>
        <h1>오늘의 인천공항</h1>
        {/* {apiData.map((item) => (<div key={item.flightId}>{item.airline}</div>))} */}
        <AirplaneSVG></AirplaneSVG>
      </Wrapper>
    </>
  )
};
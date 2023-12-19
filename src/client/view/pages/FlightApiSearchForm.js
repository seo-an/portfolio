import styled from 'styled-components';

import { GrayButtonWithSolidBorder as Button } from '../../../styles/common/Button.js';
import { ReactComponent as AirplaneSVG } from '../../../assets/icon/svg/airplane.svg';
import airlinesInfo from '../../components/data/airlines_info.json';


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
  width: 100%;
  margin: 16px 16px;
  flex-wrap: wrap;

  &.sub {
    padding: 8px 0px;
  }
`;
export const Input = styled.input `
  width: 168px;
  margin: 0px 8px;
  padding: 2px 4px;
  box-sizing : border-box;
`;
export const Select = styled.select `
  width: 60px;
  margin: 0px 8px;
  padding: 2px 4px;
  // box-sizing : border-box;
`;
export const Content = styled.div `
  display: block;

  & ul {
    margin: 16px 0;
    & li {
      line-height: 1.4em;
    }
  }
`;


export const FlightApiSearchForm = ( func ) => {
  const airlines = airlinesInfo.airline;
  const airports = airlinesInfo.airport;
  
  return (
		<>
      <Container>
        <Wrapper>
          <Title>오늘의 인천공항</Title>
          <AirplaneSVG></AirplaneSVG>
        </Wrapper>

        <Wrapper className="sub">
          <form onSubmit={func.props}>
            <label htmlFor="select">인천공항</label>
            <Select id="select">
              <option value="ARRIVAL_URL">도착</option>
              <option value="DEPARTURE_URL">출발</option>
            </Select>

            <Input type="text" id="airport" list="airportsName" placeholder="공항을 입력하세요"/>
              <datalist id="airportsName">
                {airports.map((dat) => 
                  <option key={dat.id} value={dat.airportName} />
                )}
              </datalist>

            <Input type="text" id="airline" list="airlineCompanies" placeholder="항공사를 입력하세요"/>
              <datalist id="airlineCompanies">
                {airlines.map((dat) => 
                  <option key={dat.codeICAO} value={dat.companyName} />
                )}
              </datalist>
            <Button style={{display: "inline-flex"}} type="submit">불러오기</Button>
          </form>
        </Wrapper>

      </Container>
		</>
  )
};

export default FlightApiSearchForm;
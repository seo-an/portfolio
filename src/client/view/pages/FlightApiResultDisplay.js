import styled from 'styled-components';

import { Pagination } from '../../../utils/pagination.js';

// import { GrayButtonWithSolidBorder as Button } from "../../../styles/common/Button";
// import { ReactComponent as AirplaneSVG } from "../../../assets/icon/svg/airplane.svg";
// import airlinesInfo from "../../components/data/AirlinesInfo.json"


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


export const FlightApiResultDisplay = ( conf ) => {
  const goPagination = conf.props;
  // console.log('wait...', typeof(goPagination), goPagination);
  return (
    <>
      <Container>
        <Wrapper>
          <Content>
            <Pagination props={ { ...goPagination } }/>
          </Content>
        </Wrapper>
      </Container>
    </>
  )
};

export default FlightApiResultDisplay;
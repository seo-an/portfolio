import styled, { css } from 'styled-components';

import { GrayButtonWithSolidBorder as Button } from '../../../styles/common/Button.js';
import { Pagination } from '../../../utils/pagination.js';


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

	&.w50p {
		width: 50%;
		margin: 16px 0px;
		flex-wrap: nowrap;
	}

`;
export const Content = styled.div `
	display: block;

	&.mgb10 {
		margin: 0 0 10px 0;
	}

	&.mgt10 {
		margin: 10px 0 0 0;
	}

	& button {
		margin: 0px 8px;
	}
`;
export const Input = styled.input `
  width: 168px;
  margin: 0px 8px;
  padding: 2px 4px;
  box-sizing : border-box;
`;
export const Textarea = styled.textarea `
	width: calc((168px * 2) + (8px * 2));
	height: 200px;
	margin: 0px 8px;
	padding: 4px 6px;
	line-height: 1.4em;
	box-sizing : border-box;
	resize: none;
`
export const Name = styled.div `
	display: flex;
`

export const RestApiResultDisplay = ( conf ) => {
	const goPagination = conf.props;

  return (
    <>
			<Container>
				<Wrapper>
					<Title>방명록</Title>
				</Wrapper>
				
				<Wrapper>
					<Wrapper className="w50p">
						<Content id="guestbookDisplay">
							<Pagination props={ { ...goPagination } }/>
						</Content>
					</Wrapper>
					
				</Wrapper>
				{/* <button onClick={}>삭제</button> */}
			</Container>
		</>
  )
};
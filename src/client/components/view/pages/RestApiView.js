import styled, { css } from "styled-components";

import { GrayButtonWithSolidBorder as Button } from "../common/Button";


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

	${props =>
    props.w50p &&
    css`
			width: 50%;
			margin: 16px 0px;
			flex-wrap: nowrap;
		`
	}
  
`;
export const Content = styled.div `
	display: block;

	${props =>
    props.mgb10 &&
    css`
			margin: 0 0 10px 0;
		`
	}

	${props =>
    props.mgt10 &&
    css`
			margin: 10px 0 0 0;
		`
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


export const RestApiView = ( fromRestApiJs ) => {
  // console.log('in view', fromRestApiJs.props.handleSubmit);
  
  return (
    <>
			<Container>
				<Wrapper>
					<Title>방명록</Title>
				</Wrapper>

				<Wrapper>
					<Wrapper w50p>
						<Content>
							{fromRestApiJs.props.elements}
						</Content>
					</Wrapper>

					<Wrapper w50p>
						<form onSubmit={fromRestApiJs.props.handleSubmit}>
							<Content mgb10>
								<Input type="text" id="name" placeholder="이름"></Input>
								<Input type="text" id="simple_password" placeholder="비밀번호"></Input>
							</Content>
							<Content>
								<Textarea type="text" id="comment" placeholder="내용"></Textarea>
							</Content>
							<Content mgt10>
								<Button type="submit">등록</Button>
							</Content>
						</form>
					</Wrapper>
				</Wrapper>
			</Container>
		</>
  )
};
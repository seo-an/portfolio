import { Link } from 'react-router-dom';

import styled from 'styled-components';

import { handleClickDiv } from '../../action/actionsForLinkCard.js';


export const CardContainer = styled.div `
  display: flex;
  width: 100%;
  height: 100%;
  margin: 30px 0;
  justify-content: space-evenly;

	.& hide {
		height: 400px;
		overflow: hidden;
	}
`;

export const GridContainer = styled.div `
	display: grid;
	grid-template-columns: repeat(3, 1fr);
	row-gap: 20px;
	column-gap: 10px;
`

export const CardWrapper = styled.div `
  display: flex;
  width: 200px;
  height: 200px;
	align-items: center;
	justify-content: center;
	border: 1px solid #e1e1e1;
	border-radius: 3px;
`;

export const LinkWrapper = styled.div `
  display: flex;
  width: 200px;
	height: fit-content;
	justify-content: center;
`;

export const HomeCardsView = ( props ) => {
	const data = props.props.data;

	return (
		<>
			<CardContainer>
				<GridContainer>
					{data.map( (dat) => (
						<CardWrapper key={dat.id} onClick={handleClickDiv} style={{cursor: 'pointer'}}>
							<LinkWrapper>
								<Link to={dat.link} style={{textDecoration: 'none', textDecorationColor: 'inherit', color: 'inherit', padding: '16px'}}>{dat.text}</Link>
							</LinkWrapper>
						</CardWrapper>
					) )}

					<CardWrapper>
						<LinkWrapper>
							<p style={{padding: '16px'}}>준비중 (무한 스크롤, 기간산정 기능, 그림판, 스톱워치)</p>
						</LinkWrapper>
					</CardWrapper>

				</GridContainer>
			</CardContainer>
		</>
	);
}
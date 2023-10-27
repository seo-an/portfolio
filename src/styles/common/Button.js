import styled, { css } from "styled-components";

const colorCarrot = '#ff8a34';

export const ClearButtonWithNoBorder = styled.button `
  display: flex;
  line-height: 25px;
  align-items: center;
  font-size: 0.8em;
  background-color: white;
  border-color: ${colorCarrot};
  border-width: 1px;
  border-radius: 4px;
  border-style: none;

  &:active {
    border-style: solid;
  }
`;
export const ClearButtonWithSolidBorder = styled.button `
  display: flex;
  line-height: 25px;
  align-items: center;
  font-size: 0.8em;
  background-color: white;
  border-color: #333;
  border-width: 1px;
  border-radius: 4px;
  border-style: solid;

  &:active {
		border-color: ${colorCarrot};
  }
`;
export const GrayButtonWithSolidBorder = styled.button `
  display: flex;
	${props =>
    props.inline &&
    css`
			display: inline-block;
		`
	}

  line-height: 25px;
  align-items: center;
  font-size: 0.8em;
  background-color: #efefef;
  border-color: #333;
  border-width: 1px;
  border-radius: 4px;
  border-style: solid;

  &:active {
		background-color: white;
  }
`;
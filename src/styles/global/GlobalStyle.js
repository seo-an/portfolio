import { createGlobalStyle } from "styled-components";

const GlobalStyle = createGlobalStyle `

  html, body {
    margin: 0;
    font-family: 'seoanCocktail';
    font-style: normal;
    font-size: 16px;
    color: #333;

    & #root {
      margin: 0;
      min-width: 780px;
    } 
  }

  p, h1, h2, h3, h4, h5, h6 {
    margin: 0;
  }

  ul {
    margin: 0;
    padding-inline-start: 0px;
  }

  li {
    list-style: none;
  }

  button {
    font-weight: 400;
  }

  #root {
    margin: 8px;
  }
`;

export default GlobalStyle;
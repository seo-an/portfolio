import { createGlobalStyle } from "styled-components";

const GlobalFonts = createGlobalStyle `
  @font-face {
    font-family: 'DalseoDarling';
    font-style: normal;
    font-weight: 400;
    src: local('DalseoDarling'),
          url('/fonts/DalseoDarling.woff2') format('woff2');
  }
  @font-face {
    font-family: 'DalseoDarling';
    font-style: normal;
    font-weight: 500;
    src: local('DalseoDarling'),
          url('/fonts/DalseoDarlingMedium.woff2') format('woff2');
  }
  @font-face {
    font-family: 'DalseoDarling';
    font-style: normal;
    font-weight: 700;
    src: local('DalseoDarling'),
          url('/fonts/DalseoDarlingBold.woff2') format('woff2');
  }

  @font-face {
    font-family: 'LineSeed';
    font-style: normal;
    font-weight: 100;
    src: local('LineSeed'),
          url('/fonts/LINESeedKR-Th.woff2') format('woff2');
  }
  @font-face {
    font-family: 'LineSeed';
    font-style: normal;
    font-weight: 400;
    src: local('LineSeed'),
          url('/fonts/LINESeedKR-Rg.woff2') format('woff2');
  }
  @font-face {
    font-family: 'LineSeed';
    font-style: normal;
    font-weight: 700;
    src: local('LineSeed'),
          url('/fonts/LINESeedKR-Bd.woff2') format('woff2');
  }
`;

export default GlobalFonts;
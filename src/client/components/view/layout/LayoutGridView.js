import styled from "styled-components";

export const min = 780;
export const hd = 1280; // 1280*720
export const fhd = 1920; // 1920*1080
export const qhd = 2048; // 2560*1440
export const uhd = 3839; // 3840*2160
// max, min-max, min


export const MainContainer = styled.div `
  display: flex;
  justify-content: center;


`

export const MainGrid = styled.div `
  display: grid;
  width: 100%;
  min-width: ${min}px;
  max-width: ${hd}px;

  @media screen and (max-width: ${hd}px) {
    // background-color: linen;
  }

  @media screen and (min-width: ${hd + 1}px) {
    // background-color: pink;
  }
`
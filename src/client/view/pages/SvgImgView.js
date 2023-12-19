import { forwardRef } from 'react';

import styled from 'styled-components';

import { CampingSvg as SvgCamping } from '../../../assets/image/camping/CampingSvg.js';


export const Container = styled.div `
  display: flex;
  width: 100%;
  height: 100%;
`;

export const Wrapper = styled.div `
  display: flex;
  width: 100%;
  max-width: 1280px;
  height: auto;
  margin: 8px;
  flex-wrap: wrap;
`;

export const SvgWrapper = styled.div `
  display: block;
  width: 100%;
  height: auto;
`;


// color set
export const dawn = [
  {
    layer: "gradient",
    color: ["#17122a", "#231938", "#281939", "#381f40", "#5c2d51", "#6c3a58", "#965b69", "#cd8780", "#d5978b", "#e8c0a8", "#efceb1"],
    option: {},
  }, {
    layer: "stars",
    color: ["#fef9c8", "#e4ddcc"],
    option: {
      opacity: {
        shining: {
          normal: 1.0,
          shine: 1.0,
        },
        subdued: {
          normal: 0.4,
          less: 0.1,
        }
      },
    }
  }, {
    layer: "solunar",
    color: ["#f4dfbb", "#e0ceb6"],
    option: {
      main: {cx: 578.188, cy: 213.605, r: 29.588,},
      craterOne: {cx: 588.944, cy: 197.887, r: 5.076,},
      craterTwo: {cx: 596.515, cy: 207.649, r: 2.511,},
      craterThree: {cx: 585.882, cy: 212.639, r: 3.223,},
    },
  }, {
    layer: "",
    color: [],
    option: {
    },
  }
];

export const morning = [
  {
    layer: "gradient",
    color: ["#003850", "#09385c", "#0d3451", "#12384d", "#3a4a4c", "#4f5353", "#966744", "#b59682", "#d2a87a", "#E8C0A8", "#EFCEB1"],
    option: {},
  }, {
    layer: "stars",
    color: ["#fef9c8", "transparent"],
    option: {
      opacity: {
        shining: {
          normal: 0,
          shine: 0.1,
        },
        subdued: {
          normal: 0,
          less: 0,
        }
      },
    }
  }, {
    layer: "solunar",
    color: ["#ffe9bc", "#ffc758"],
    option: {
      main: {cx: 178.188, cy: 213.605, r: 29.588,},
      craterOne: {cx: 178.188, cy: 213.605, r: 28.85,},
      craterTwo: {cx: 0, cy: 0, r: 0,},
      craterThree: {cx: 0, cy: 0, r: 0,},
    },
  }
];




export const SvgImgView = forwardRef((props, ref) => {
  
  const colorSet = morning;

  return (
    <>
      <Container ref={ref}>
        <Wrapper>

          <SvgWrapper>
            <SvgCamping getData={props.getData} setData={props.setData} colorset={colorSet} data={props.data} />
          </SvgWrapper>

        </Wrapper>
      </Container>
    </>
  )
});
import { useState } from "react";

import styled from "styled-components";

import { isNotNull, isThisNumber } from './detectDataType.js';
import { arraySplitting } from './arraySplitting.js';
import { addClassRemainClass } from './toggleClasses.js';


/**
 * raw 데이터로 보여주고 싶은 항목에 대해 html 태그와 함께 정리하여 array에 담음
 * array를 아래 object처럼 양식을 갖춰 Pagination props에 포함시켜 전달함
 * 
 * const goPagination = {
 *  data: 데이터(array),
 *  pageSize: 한 페이지에 보여줄 데이터의 수,
 *  paginationSize: 이전 이후 버튼으로 나눌 pagenation 기준 (ex. 10개가 넘어가면 이전 이후 버튼으로 넘기겠다)
 * };
 * 
 * Pagination에서 전달 받은 데이터를 dataProcessing 함수로 보내 가공함
 * dataProcessing(데이터, pageSize, paginationsSize, pagination 숫자의 onClick이벤트 핸들러);
 * 
 * 데이터 준비 끝
*/



export const GoFront = styled.button `
	display: flex;
	align-items: center;
	margin: 0px 16px 0px 8px;
	cursor: pointer;
`;
export const GoRear = styled.button `
	display: flex;
	align-items: center;
	margin: 0px 8px 0px 16px;
	cursor: pointer;
`;
export const Numbers = styled.button `
	margin: 4px;
	cursor: pointer;

	&.selected {
		color: rgb(243, 114, 25, 1); //#f37219
		font-weight: bold;
	}

	& span {
		display: flex;
		width: 24px;
		align-items: center;
		justify-content: center;
	}
`;
export const PaginationWrap = styled.div `
	display: flex;
	width: 100%;
	padding: 16px 0px;
	justify-content: center;
	flex-wrap: nowrap;
`;
export const ContentsWrapper = styled.div `
	&.flight {
		display: flex;
		margin: 0px 8px;

		&:first-child {
			margin: 8px 8px 0px 8px;
		}

		& ul {
			margin: 8px 0px;
			& li {
				line-height: 1.6em;
			}
		}
	}

	&.guestBook {
		display: flex;
		margin: 8px 8px 16px 8px;
		flex-wrap: wrap;

		&:first-child {
			margin: 16px 8px 16px 8px;
		}

		.forName {
			display: flex;
			width: 100%;
		}
	
		.forDate {
			display: flex;
			width: 100%;
		}
	
		.forContent {
			display: flex;
			margin-top: 4px;
			width: 100%;
		}
	}
`

export const List = styled.div `
  display: flex;
`


// export const toggleClass = ( parent, child, classNametag ) => {

// 	const len = parent.children.length;

//   for (let i = 0; i < len; i++) {
//     if (parent.children[i].classList.contains(classNametag)) {
//       parent.children[i].classList.remove(classNametag);
//     }
//   }
//   child.classList.add(classNametag);

//   return child;
// };


const dataProcessing = (jsonData, pageSize, paginationSize, handleEvent) => {
  if (jsonData === undefined || jsonData === null || jsonData.length === 0) return; // 예외처리
  const items = jsonData;

	const _pageSize = (isThisNumber(pageSize) ? pageSize : null);
  const _paginationSize = (isThisNumber(paginationSize) ? paginationSize : isNotNull);
  
  if (_pageSize === null || _paginationSize === null) return; // 예외처리

  const split = arraySplitting(items, _pageSize);

  const ready = split.reduce((acc, curr, index) => {
    if (index%10 === 0) {
      acc.items.push(curr);
      acc.pages.push(<button key={`num${index}`} className="selected" onClick={handleEvent} value={index+1}>{index+1}</button>);
    } else {
      acc.items.push(curr);
      acc.pages.push(<button key={`num${index}`} className="" onClick={handleEvent} value={index+1}>{index+1}</button>);
    }
    return acc;
  }, { items: [], pages: [] });

  return ready;
};


export const Pagination = ( props ) => {
  
  const nowOnPage = (event) => {
    event.preventDefault();
    const grandParent = event.currentTarget.closest('#paginationNumbers');
    const parent = event.target;
		const label = 'selected';
		const val = (parent.textContent) - 1;
		setNowPage(val);

		addClassRemainClass(grandParent, parent, label);
    // console.log(val);
    return;
  };

  const turnToPage = (event) => {
    event.preventDefault();
    const id = event.target.id;
    const pageGroupSize = Math.ceil((raw.length/_pageSize)/_paginationSize); // 총 페이지 그룹 수 (이전 criteria)
    
    // console.log('now in turnToPage() : ', pageGroupSize, pageGroup, nowPage, _paginationSize < nowPage);
    if (id === 'prev') {
      if (_paginationSize < nowPage) {
        // console.log('prev', '1');
        setNowPage(0);
      }
      if (pageGroupSize === pageGroup || pageGroupSize < pageGroup) {
        const num = ((pageGroupSize - 2) < 0) ? 0 : (pageGroupSize - 2);
        // console.log('prev', '2', pageGroupSize, pageGroup, num);
        setPageGroup(num);
        setNowPage(0);
        return;
      }
      if (pageGroup < 1) {
        // console.log('prev', '3');
        setPageGroup(0); 
        setNowPage(0);
        return;
      }
      // console.log('prev', pageGroup, nowPage);
      // console.log('prev', '4');
      setPageGroup(pageGroup - 1);
      setNowPage((pageGroup - 1)*_paginationSize);
      return;
    } else if (id === 'next') {
      if(pageGroupSize === pageGroup || pageGroupSize < pageGroup) {
        // console.log('next', '1');
        setPageGroup(pageGroupSize);
        return;
      }
      
      // console.log('next', '2');
      setPageGroup(pageGroup + 1);
      setNowPage((pageGroup + 1)*_paginationSize);
      // console.log('next', pageGroup, nowPage, (pageGroup+1)*_paginationSize);
      return;
    };
  }


  const [nowPage, setNowPage] = useState(0); // 현재 페이지
	const [pageGroup, setPageGroup] = useState(0); // pagination size 단위로 이동

  if (props.props.data === 'nothing') {
    return (
      <p>결과가 존재하지 않습니다.</p>
    );
  }

  const raw = ((props.props.data) ? props.props.data : null);
  const len = (!(raw === null) ? raw.length : 0);
  const _pageSize = props.props.pageSize;
  const _paginationSize = props.props.paginationSize; // interval
  const cooking = dataProcessing(raw, _pageSize, _paginationSize, nowOnPage); // flightData
  
  const items = ((cooking) ? cooking.items : null);
  const pages = ((cooking) ? cooking.pages : null);
  // items[페이지 숫자][각 항목 index]
  // pages[페이지 숫자]
  if (items === null || pages === null) return; // 예외처리

  const totalPages = pages.length; // pages 개수
  const pageGroupSize = Math.ceil((len/_pageSize)/_paginationSize); // pages를 그룹화(pagination size로 자름) 한 수

  return (
    <>
      <div id="paginationItems">
        {
          <>{items[nowPage]}</>
        } 
      </div>
      <PaginationWrap id="paginationNumbers">
        { (totalPages < _paginationSize || totalPages === _paginationSize) ? (
          <>
            {pages}
          </> ) : (
            // 전체 페이지 그룹의 사이즈가 1 이상이고 (이전, 이후 버튼이 필요함) && 현재 첫 번째 페이지 그룹에 있을 때
            (pageGroupSize > 1 && pageGroup === 0) ? (
              <>
                {<>{pages.slice(pageGroup*_paginationSize,(pageGroup+1)*_paginationSize)}</>}
                <GoRear className={`rear`} id="next" onClick={turnToPage}>{`>`}</GoRear>
              </> 
            ) : (
              // 현재 두 번째 이상의 페이지 그룹에 있고 (한 번 이상 > 버튼을 눌렀고) && 이 이후로 더 이상 페이지 그룹이 없을 때
              (pageGroup > 0 && pageGroup === (pageGroupSize - 1)) ? (
                <>
                  <GoFront id="prev" onClick={turnToPage}>{`<`}</GoFront>
                  {<>{pages.slice(pageGroup*_paginationSize,(pageGroup+1)*_paginationSize)}</>}
                </>
              ) : (
                <>
                  <GoFront id="prev" onClick={turnToPage}>{`<`}</GoFront>
                  {<>{pages.slice(pageGroup*_paginationSize,(pageGroup+1)*_paginationSize)}</>}
                  <GoRear className={`rear`} id="next" onClick={turnToPage}>{`>`}</GoRear>
                </>
              )
            )
          )
        }
      </PaginationWrap>
    </>
  );

};
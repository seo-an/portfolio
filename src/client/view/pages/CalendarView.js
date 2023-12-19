import styled from 'styled-components';

import { CalendarReactJsPowered as reactCalendar } from '../../components/component/CalendarReactJsPowered.js';

export const colorSun = '#ef6464';
export const colorSat = '#5252eb';
export const colorDefault = '#333';


export const Container = styled.div `
  display: flex;
  width: ${(props) => {
    if(props.left) return '140px;';
    if(props.right || props.main) return '100%';
  }};
  height: 100%;
  flex-wrap: wrap;
  align-content: flex-start;
`;

export const Wrapper = styled.div `
  display: flex;
  width: 100%;
  margin: 8px;
`;

export const Title = styled.div `
  display: flex;
  width: 100%;
  margin: 8px;
  justify-content: ${props => (props.right ? 'flex-end' : (props.between ? 'space-between' : 'normal'))};
  align-items: center;

  &:before {
    ${(props) => {
      if (props.pseudoBefore) {
        return `
          width: 0;
          height: 0;
          content: '';
          border-left: 19px solid transparent;
          border-top: 19px solid transparent;
          border-bottom: 19px solid transparent;
          border-right: 28.5px solid #bbbb7c;
        `;
      }
    }
  }
`;


// Calendar
export const Year = styled.div `
  display: flex;
  height: 38px;
  width: calc(120px - 16px);
  padding-right: 16px;
  align-items: center;
  justify-content: flex-end;
  font-size: 1.6em;
  background-color: #bbbb7c;
  color: white;
`;

export const Month = styled.div `
  display: flex;
  width: calc(100% - 24px);
  height: 80px;
  margin: 0 16px 0 8px;
  justify-content: center;
  align-items: center;
  font-size: 4em;
`;

export const GridTable = styled.div `
  display: grid;
  width: 100%;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
`;
// grid-template-columns: repeat(7, minmax(100px, 1fr));
// grid-template-rows: repeat(6, 100px);

export const TableCell = styled.div `
  display: flex;
  height: 100px;
  border: ${props => (props.point ? '1px solid #e3e3e3' : 'none')};
  opacity: ${props => (props.over ? 0.4 : 1)};
`;

export const TableCellText = styled.div `
  display: block;
  width: ${props => (props.day ? 'calc(100%-16px)' : '100%')};
  height: fit-content;
  padding: 8px;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: ${props => (props.sun ? colorSun : (props.sat ? colorSat : colorDefault))};
`;


export const ButtonContainer = styled.div `
  display: flex;
  width: 100%;
  height: fit-content;
  margin: 8px;
  justify-content: space-between;
`;

export const Button = styled.div `
  display: flex;
  line-height: 25px;
  height: 25px;
  align-items: center;
  justify-content: center;
  padding: 0px 8px;
  font-size: 0.8em;
  background-color: white;
  color: #939393;
  border-style: none;

  cursor: pointer;

  &:active {
    // box-shadow: 2px 2px 1px #bfbfbf;
    border-radius: 0px;
    border-bottom: 1px solid #bfbfbf;
  }
`;
// text-shadow: 2px 0px 1px #bfbfbf;


export const CalendarView = () => {
  const reactCalendarPage = reactCalendar();

  return (
    <>
      <div>
        <h1>리액트 캘린더</h1>
        <Container main>

          <Title right pseudoBefore>
            <Year>{reactCalendarPage.year}</Year>
          </Title>

          <Wrapper>
            <Container left>
              <Month>{(reactCalendarPage.month < 10 ? ('0' + reactCalendarPage.month) : reactCalendarPage.month)}</Month>
              <ButtonContainer>
                <Button onClick={reactCalendarPage.flipOver}>{reactCalendarPage.buttonText.prev}</Button>
                <Button onClick={reactCalendarPage.flipOver}>{reactCalendarPage.buttonText.today}</Button>
                <Button onClick={reactCalendarPage.flipOver}>{reactCalendarPage.buttonText.next}</Button>
              </ButtonContainer>
            </Container>

            <Container right>
              <GridTable>
                {reactCalendarPage.week.map((item, index) => (<TableCellText day key={index}>{item}</TableCellText>))}
                {reactCalendarPage.calendarPage.map((item) => { 
                  if (item.month < reactCalendarPage.month - 1 || item.month > reactCalendarPage.month - 1) {
                    return (<TableCell over key={item.id}>
                      {item.day === 0 ? <TableCellText sun>{item.date}</TableCellText> : (item.day === 6 ? <TableCellText sat>{item.date}</TableCellText> : (<TableCellText>{item.date}</TableCellText>))}
                    </TableCell>)
                  } else if (item.onToday) {
                    return (<TableCell point key={item.id}>
                      {item.day === 0 ? <TableCellText sun>{item.date}</TableCellText> : (item.day === 6 ? <TableCellText sat>{item.date}</TableCellText> : (<TableCellText>{item.date}</TableCellText>))}
                    </TableCell>)
                  } else {
                    return (<TableCell key={item.id}>
                      {item.day === 0 ? <TableCellText sun>{item.date}</TableCellText> : (item.day === 6 ? <TableCellText sat>{item.date}</TableCellText> : (<TableCellText>{item.date}</TableCellText>))}
                    </TableCell>)
                  }
                })}
              </GridTable>
            </Container>
          </Wrapper>

        </Container>
      </div>
    </>
  )
};
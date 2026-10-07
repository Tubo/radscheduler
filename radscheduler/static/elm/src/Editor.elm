port module Editor exposing (main)

{-| The roster editor: registrars by dates for three weeks, with shifts and leave in each cell.

The data comes from /api/editor/roster in one request, through the client generated from the API's
OpenAPI schema (`devenv shell -- elm:api`). The grid is the instrument: every cell is one keyboard stop
(arrow keys move, Enter opens it, a shift's key adds or changes that shift), and its menu opens in a
fixed layer over the grid, drawn only while open and never clipped by the scroll area.

-}

import Browser
import Browser.Dom as Dom
import Browser.Events
import Date exposing (Date)
import Dict exposing (Dict)
import Html exposing (..)
import Html.Attributes exposing (..)
import Html.Events exposing (on, onCheck, onClick, onFocus, onInput, onSubmit, preventDefaultOn, targetValue)
import Json.Decode as Decode exposing (Decoder)
import Json.Encode as Encode
import OpenApi.Common exposing (Nullable(..))
import Process
import Radscheduler.Api as Api
import Radscheduler.Types as T
import Set exposing (Set)
import Task
import Time


port pushUrl : String -> Cmd msg


port onUrlChange : (String -> msg) -> Sub msg


port saveFilters : Encode.Value -> Cmd msg


main : Program Decode.Value Model Msg
main =
    Browser.element
        { init = init
        , update = update
        , view = view
        , subscriptions = subscriptions
        }



-- MODEL


{-| A shift or leave type as the page describes it: stored value, full label, short label for the grid,
and the key that picks it (empty for leave). Labels live on the server so other departments can differ.
-}
type alias Choice =
    { value : String
    , label : String
    , short : String
    , key : String
    }


type alias Flags =
    { csrfToken : String
    , week : String
    , editorUrl : String
    , shiftTypes : List Choice
    , leaveTypes : List Choice
    , cover : List String
    , hiddenShiftTypes : List String
    , hiddenLeaveTypes : List String
    }


type alias Model =
    { flags : Flags
    , week : Date
    , zone : Time.Zone
    , roster : Maybe T.RosterOut
    , loading : Bool
    , hiddenShiftTypes : Set String
    , hiddenLeaveTypes : Set String
    , cursor : Maybe Cell
    , popover : Maybe Popover
    , publish : Maybe PublishDraft
    , saving : Set Cell
    , failure : Maybe Failure
    , announcement : String
    }


{-| A grid cell: registrar id and the day as a Rata Die number, so it can key sets and dicts.
-}
type alias Cell =
    ( Int, Int )


type Popover
    = CellMenu Cell Anchor (Maybe Int)
    | FiltersMenu Anchor
    | KeyMenu Anchor


{-| Where the element that opened a popover sits in the viewport.
-}
type alias Anchor =
    { left : Float
    , top : Float
    , bottom : Float
    , viewportWidth : Float
    , viewportHeight : Float
    }


type PopoverTarget
    = ForCell Cell (Maybe Int)
    | ForFilters
    | ForKey


{-| The publish dialog edits ISO date strings, straight from the date inputs.
-}
type alias PublishDraft =
    { start : String
    , end : String
    , preview : Maybe T.PreviewOut
    , saving : Bool
    }


type alias Failure =
    { message : String
    , retry : Maybe Msg
    , cell : Maybe Cell
    }


{-| Errors from the generated client. Most endpoints declare no error body, hence `Never`.
-}
type alias ApiError =
    OpenApi.Common.Error Never String


choiceDecoder : Decoder Choice
choiceDecoder =
    Decode.map4 Choice
        (Decode.field "value" Decode.string)
        (Decode.field "label" Decode.string)
        (Decode.field "short" Decode.string)
        (Decode.field "key" Decode.string)


flagsDecoder : Decoder Flags
flagsDecoder =
    Decode.map8 Flags
        (Decode.field "csrfToken" Decode.string)
        (Decode.field "week" Decode.string)
        (Decode.field "editorUrl" Decode.string)
        (Decode.field "shiftTypes" (Decode.list choiceDecoder))
        (Decode.field "leaveTypes" (Decode.list choiceDecoder))
        (Decode.field "cover" (Decode.list Decode.string))
        (optionalList "hiddenShiftTypes")
        (optionalList "hiddenLeaveTypes")


optionalList : String -> Decoder (List String)
optionalList field =
    Decode.oneOf [ Decode.field field (Decode.list Decode.string), Decode.succeed [] ]


init : Decode.Value -> ( Model, Cmd Msg )
init value =
    case Decode.decodeValue flagsDecoder value |> Result.mapError Decode.errorToString |> Result.andThen withWeek of
        Ok ( flags, week ) ->
            let
                model =
                    initialModel flags week
            in
            ( model, Cmd.batch [ getRoster model week, Task.perform GotZone Time.here ] )

        Err err ->
            let
                model =
                    initialModel (Flags "" "" "" [] [] [] [] []) (Date.fromRataDie 1)
            in
            ( { model | loading = False, failure = Just (Failure ("The editor couldn't start: " ++ err) Nothing Nothing) }
            , Cmd.none
            )


withWeek : Flags -> Result String ( Flags, Date )
withWeek flags =
    Date.fromIsoString flags.week |> Result.map (Tuple.pair flags)


initialModel : Flags -> Date -> Model
initialModel flags week =
    { flags = flags
    , week = week
    , zone = Time.utc
    , roster = Nothing
    , loading = True
    , hiddenShiftTypes = Set.fromList flags.hiddenShiftTypes
    , hiddenLeaveTypes = Set.fromList flags.hiddenLeaveTypes
    , cursor = Nothing
    , popover = Nothing
    , publish = Nothing
    , saving = Set.empty
    , failure = Nothing
    , announcement = ""
    }



-- REQUESTS


auth : Model -> { x_csrftoken : String }
auth model =
    { x_csrftoken = model.flags.csrfToken }


getRoster : Model -> Date -> Cmd Msg
getRoster model week =
    Api.getRoster { authorization = auth model, toMsg = GotRoster week, params = { week = week } }


errorMessage : (err -> Maybe String) -> OpenApi.Common.Error err String -> String
errorMessage known error =
    case error of
        OpenApi.Common.BadUrl url ->
            "Bad URL: " ++ url

        OpenApi.Common.Timeout ->
            "The server took too long to respond."

        OpenApi.Common.NetworkError ->
            "Couldn't reach the server. Check your connection."

        OpenApi.Common.KnownBadStatus _ body ->
            known body |> Maybe.withDefault "The server rejected the change."

        OpenApi.Common.UnknownBadStatus metadata _ ->
            statusMessage metadata.statusCode

        OpenApi.Common.BadErrorBody metadata _ ->
            statusMessage metadata.statusCode

        OpenApi.Common.BadBody _ _ ->
            "The server sent a response the editor didn't understand. Reload the page."


statusMessage : Int -> String
statusMessage status =
    case status of
        401 ->
            "You've been signed out. Reload the page to sign in again."

        403 ->
            "The server refused the change. Reload the page and try again."

        404 ->
            "That item no longer exists. Reload the page to see the latest roster."

        _ ->
            "Something went wrong on the server (" ++ String.fromInt status ++ "). Try again; if it keeps failing, reload the page."


apiError : ApiError -> String
apiError =
    errorMessage never



-- UPDATE


type Msg
    = GotRoster Date (Result ApiError T.RosterOut)
    | GotZone Time.Zone
    | GoToWeek Date
    | PickWeek String
    | Reload
    | UrlChanged String
    | ToggleShiftType String Bool
    | ToggleLeaveType String Bool
    | ShowAllTypes
    | Focused Cell
    | GridKey String
    | Open PopoverTarget String
    | GotAnchor PopoverTarget (Result Dom.Error Dom.Element)
    | ClosePopover
    | AddShift Cell T.ShiftType
    | ChangeShift Cell Int T.ShiftPatch
    | AskDelete Cell Int
    | DeleteShift Cell Int
    | GotShift Cell Msg (Result ApiError T.ShiftOut)
    | ShiftDeleted Cell Msg Int (Result ApiError T.ShiftOut)
    | ChangeLeave Cell Int T.LeavePatch
    | GotLeave Cell Msg (Result ApiError T.LeaveOut)
    | OpenPublish
    | SetPublishStart String
    | SetPublishEnd String
    | GotPreview ( String, String ) (Result ApiError T.PreviewOut)
    | SavePublish
    | GotPublished (Result (OpenApi.Common.Error T.ErrorOut String) T.PublishedRange)
    | ClosePublish
    | Retry Msg
    | DismissFailure
    | FocusId String
    | NoOp


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        GotRoster week result ->
            if week /= model.week then
                -- A newer week was asked for while this one loaded.
                ( model, Cmd.none )

            else
                case result of
                    Ok roster ->
                        ( { model | roster = Just roster, loading = False, announcement = "Showing " ++ windowLabel roster.dates }
                        , Cmd.none
                        )

                    Err err ->
                        ( { model | loading = False, failure = Just (Failure ("Couldn't load the roster. " ++ apiError err) (Just Reload) Nothing) }
                        , Cmd.none
                        )

        GotZone zone ->
            ( { model | zone = zone }, Cmd.none )

        GoToWeek week ->
            if week == model.week then
                ( model, Cmd.none )

            else
                load week model
                    |> withCmd (pushUrl (model.flags.editorUrl ++ Date.toIsoString week ++ "/"))

        PickWeek value ->
            case Date.fromIsoString value of
                Ok week ->
                    update (GoToWeek week) model

                Err _ ->
                    ( model, Cmd.none )

        Reload ->
            load model.week model

        UrlChanged path ->
            case weekFromPath path of
                Just week ->
                    if week == model.week then
                        ( model, Cmd.none )

                    else
                        load week model

                Nothing ->
                    ( model, Cmd.none )

        ToggleShiftType value shown ->
            persistFilters { model | hiddenShiftTypes = toggle value shown model.hiddenShiftTypes }

        ToggleLeaveType value shown ->
            persistFilters { model | hiddenLeaveTypes = toggle value shown model.hiddenLeaveTypes }

        ShowAllTypes ->
            persistFilters { model | hiddenShiftTypes = Set.empty, hiddenLeaveTypes = Set.empty }

        Focused cell ->
            ( { model | cursor = Just cell }, Cmd.none )

        GridKey key ->
            case ( model.cursor, model.roster ) of
                ( Just cell, Just roster ) ->
                    gridKey key cell roster model

                _ ->
                    ( model, Cmd.none )

        Open target elementId ->
            ( model, Task.attempt (GotAnchor target) (Dom.getElement elementId) )

        GotAnchor target (Ok element) ->
            let
                anchor =
                    { left = element.element.x - element.viewport.x
                    , top = element.element.y - element.viewport.y
                    , bottom = element.element.y - element.viewport.y + element.element.height
                    , viewportWidth = element.viewport.width
                    , viewportHeight = element.viewport.height
                    }
            in
            case target of
                ForCell cell confirm ->
                    ( { model | popover = Just (CellMenu cell anchor confirm), cursor = Just cell }
                    , focusSoon
                        (if confirm == Nothing then
                            "popover-first"

                         else
                            "confirm-delete"
                        )
                    )

                ForFilters ->
                    ( { model | popover = Just (FiltersMenu anchor) }, focusSoon "popover-first" )

                ForKey ->
                    ( { model | popover = Just (KeyMenu anchor) }, focusSoon "popover-first" )

        GotAnchor _ (Err _) ->
            ( model, Cmd.none )

        ClosePopover ->
            closePopover model

        AddShift (( registrar, dayNumber ) as cell) shiftType ->
            closePopover (startSaving cell model)
                |> withCmd
                    (Api.addShift
                        { authorization = auth model
                        , toMsg = GotShift cell msg
                        , body = { date = Date.fromRataDie dayNumber, registrar = registrar, type_ = shiftType, extra_duty = Nothing }
                        }
                    )

        ChangeShift cell shiftId patch ->
            closePopover (startSaving cell model)
                |> withCmd (Api.changeShift { authorization = auth model, toMsg = GotShift cell msg, body = patch, params = { shift_id = shiftId } })

        AskDelete cell shiftId ->
            case model.popover of
                Just (CellMenu c anchor _) ->
                    ( { model | popover = Just (CellMenu c anchor (Just shiftId)) }, focusSoon "confirm-delete" )

                _ ->
                    ( model, openCell cell (Just shiftId) )

        DeleteShift cell shiftId ->
            closePopover (startSaving cell model)
                |> withCmd (Api.deleteShift { authorization = auth model, toMsg = ShiftDeleted cell msg shiftId, params = { shift_id = shiftId } })

        GotShift cell _ (Ok shift) ->
            ( finishSaving cell ("Saved " ++ shiftLabel model shift.type_ ++ " for " ++ describeCell model cell ++ ".") model
                |> updateRoster (\r -> { r | shifts = upsert shift r.shifts })
            , Cmd.none
            )

        ShiftDeleted cell _ shiftId (Ok _) ->
            ( finishSaving cell ("Deleted the shift for " ++ describeCell model cell ++ ".") model
                |> updateRoster (\r -> { r | shifts = List.filter (\s -> s.id /= shiftId) r.shifts })
            , Cmd.none
            )

        ChangeLeave cell leaveId patch ->
            ( startSaving cell model
            , Api.changeLeave { authorization = auth model, toMsg = GotLeave cell msg, body = patch, params = { leave_id = leaveId } }
            )

        GotLeave cell _ (Ok leave) ->
            ( finishSaving cell ("Saved the leave for " ++ describeCell model cell ++ ".") model
                |> updateRoster (\r -> { r | leaves = upsert leave r.leaves })
            , Cmd.none
            )

        GotShift cell retry (Err err) ->
            ( saveFailed cell retry err model, Cmd.none )

        ShiftDeleted cell retry _ (Err err) ->
            ( saveFailed cell retry err model, Cmd.none )

        GotLeave cell retry (Err err) ->
            ( saveFailed cell retry err model, Cmd.none )

        OpenPublish ->
            let
                ( start, end ) =
                    case model.roster |> Maybe.andThen (.published >> nullable) of
                        Just range ->
                            ( range.start, range.end )

                        Nothing ->
                            ( model.week, model.week )
            in
            updateDraft identity
                { model
                    | publish = Just { start = Date.toIsoString start, end = Date.toIsoString end, preview = Nothing, saving = False }
                    , popover = Nothing
                }
                |> withCmd (focusSoon "publish-start")

        SetPublishStart start ->
            updateDraft (\d -> { d | start = start }) model

        SetPublishEnd end ->
            updateDraft (\d -> { d | end = end }) model

        GotPreview range (Ok preview) ->
            case model.publish of
                Just draft ->
                    if ( draft.start, draft.end ) == range then
                        ( { model | publish = Just { draft | preview = Just preview } }, Cmd.none )

                    else
                        ( model, Cmd.none )

                Nothing ->
                    ( model, Cmd.none )

        GotPreview _ (Err _) ->
            ( model, Cmd.none )

        SavePublish ->
            case Maybe.andThen (\d -> draftRange d |> Maybe.map (Tuple.pair d)) model.publish of
                Just ( draft, range ) ->
                    if draft.saving then
                        ( model, Cmd.none )

                    else
                        ( { model | publish = Just { draft | saving = True } }
                        , Api.setPublished { authorization = auth model, toMsg = GotPublished, body = range }
                        )

                Nothing ->
                    ( model, Cmd.none )

        GotPublished (Ok published) ->
            ( updateRoster (\r -> { r | published = Present published })
                { model | publish = Nothing, announcement = "Published " ++ fullDate published.start ++ " to " ++ fullDate published.end ++ "." }
            , focusSoon "publish-button"
            )

        GotPublished (Err err) ->
            ( { model
                | publish = Maybe.map (\d -> { d | saving = False }) model.publish
                , failure = Just (Failure ("Couldn't publish. " ++ errorMessage (.detail >> Just) err) (Just SavePublish) Nothing)
              }
            , Cmd.none
            )

        ClosePublish ->
            ( { model | publish = Nothing }, focusSoon "publish-button" )

        Retry retryMsg ->
            update retryMsg { model | failure = Nothing }

        DismissFailure ->
            ( { model | failure = Nothing }, Cmd.none )

        FocusId elementId ->
            ( model, focus elementId )

        NoOp ->
            ( model, Cmd.none )


{-| Arrow keys move, Home and End jump along the row, Enter opens the cell, a shift's key adds or changes
that shift, and Delete asks to delete the cell's shift.
-}
gridKey : String -> Cell -> T.RosterOut -> Model -> ( Model, Cmd Msg )
gridKey key (( registrar, current ) as cell) roster model =
    let
        rows =
            List.map .id roster.registrars

        days =
            List.map Date.toRataDie roster.dates

        move rowStep colStep =
            jump ( step rowStep registrar rows, step colStep current days ) model

        shifts =
            cellShifts roster cell
    in
    case key of
        "ArrowUp" ->
            move -1 0

        "ArrowDown" ->
            move 1 0

        "ArrowLeft" ->
            move 0 -1

        "ArrowRight" ->
            move 0 1

        "Home" ->
            jump ( registrar, List.head days |> Maybe.withDefault current ) model

        "End" ->
            jump ( registrar, List.reverse days |> List.head |> Maybe.withDefault current ) model

        "Enter" ->
            ( model, openCell cell Nothing )

        " " ->
            ( model, openCell cell Nothing )

        "Delete" ->
            deleteKey cell shifts model

        "Backspace" ->
            deleteKey cell shifts model

        _ ->
            case List.filter (\( _, c ) -> c.key == String.toLower key) (shiftChoices model) of
                ( shiftType, _ ) :: _ ->
                    case shifts of
                        [] ->
                            update (AddShift cell shiftType) model

                        [ shift ] ->
                            if shift.type_ == shiftType then
                                ( model, Cmd.none )

                            else
                                update (ChangeShift cell shift.id { type_ = Just shiftType, extra_duty = Nothing }) model

                        _ ->
                            ( model, openCell cell Nothing )

                [] ->
                    ( model, Cmd.none )


deleteKey : Cell -> List T.ShiftOut -> Model -> ( Model, Cmd Msg )
deleteKey cell shifts model =
    case shifts of
        [ shift ] ->
            ( model, openCell cell (Just shift.id) )

        [] ->
            ( model, Cmd.none )

        _ ->
            ( model, openCell cell Nothing )


jump : Cell -> Model -> ( Model, Cmd Msg )
jump target model =
    ( { model | cursor = Just target }, focus (cellId target) )


{-| The neighbour `offset` places along `items`, stopping at either end.
-}
step : Int -> a -> List a -> a
step offset current items =
    let
        indexed =
            List.indexedMap Tuple.pair items

        index =
            indexed |> List.filter (\( _, item ) -> item == current) |> List.head |> Maybe.map Tuple.first |> Maybe.withDefault 0

        target =
            clamp 0 (List.length items - 1) (index + offset)
    in
    indexed |> List.filter (\( i, _ ) -> i == target) |> List.head |> Maybe.map Tuple.second |> Maybe.withDefault current


openCell : Cell -> Maybe Int -> Cmd Msg
openCell cell confirm =
    Task.attempt (GotAnchor (ForCell cell confirm)) (Dom.getElement (cellId cell))


closePopover : Model -> ( Model, Cmd Msg )
closePopover model =
    case model.popover of
        Just (CellMenu cell _ _) ->
            ( { model | popover = Nothing }, focus (cellId cell) )

        Just (FiltersMenu _) ->
            ( { model | popover = Nothing }, focus "filters-button" )

        Just (KeyMenu _) ->
            ( { model | popover = Nothing }, focus "key-button" )

        Nothing ->
            ( model, Cmd.none )


withCmd : Cmd Msg -> ( Model, Cmd Msg ) -> ( Model, Cmd Msg )
withCmd cmd ( model, other ) =
    ( model, Cmd.batch [ other, cmd ] )


focus : String -> Cmd Msg
focus elementId =
    Task.attempt (\_ -> NoOp) (Dom.focus elementId)


{-| Focus an element that the next render will draw.
-}
focusSoon : String -> Cmd Msg
focusSoon elementId =
    Process.sleep 30 |> Task.andThen (\_ -> Dom.focus elementId) |> Task.attempt (\_ -> NoOp)


load : Date -> Model -> ( Model, Cmd Msg )
load week model =
    ( { model | week = week, loading = True, popover = Nothing, announcement = "Loading…" }, getRoster model week )


persistFilters : Model -> ( Model, Cmd Msg )
persistFilters model =
    ( model
    , saveFilters
        (Encode.object
            [ ( "hiddenShiftTypes", Encode.list Encode.string (Set.toList model.hiddenShiftTypes) )
            , ( "hiddenLeaveTypes", Encode.list Encode.string (Set.toList model.hiddenLeaveTypes) )
            ]
        )
    )


updateDraft : (PublishDraft -> PublishDraft) -> Model -> ( Model, Cmd Msg )
updateDraft f model =
    case model.publish of
        Just draft ->
            let
                changed =
                    f { draft | preview = Nothing }
            in
            ( { model | publish = Just changed }
            , case draftRange changed of
                Just range ->
                    Api.previewPublished
                        { authorization = auth model
                        , toMsg = GotPreview ( changed.start, changed.end )
                        , params = { start = range.start, end = range.end }
                        }

                Nothing ->
                    Cmd.none
            )

        Nothing ->
            ( model, Cmd.none )


{-| The draft as a range, if both dates parse and the start isn't after the end.
-}
draftRange : PublishDraft -> Maybe T.PublishedRange
draftRange draft =
    case ( Date.fromIsoString draft.start, Date.fromIsoString draft.end ) of
        ( Ok start, Ok end ) ->
            if Date.compare start end /= GT then
                Just { start = start, end = end }

            else
                Nothing

        _ ->
            Nothing


startSaving : Cell -> Model -> Model
startSaving cell model =
    { model | saving = Set.insert cell model.saving, failure = Nothing, announcement = "Saving…" }


finishSaving : Cell -> String -> Model -> Model
finishSaving cell announcement model =
    { model | saving = Set.remove cell model.saving, announcement = announcement }


saveFailed : Cell -> Msg -> ApiError -> Model -> Model
saveFailed cell retry err model =
    { model
        | saving = Set.remove cell model.saving
        , failure = Just (Failure ("Couldn't save the change for " ++ describeCell model cell ++ ". " ++ apiError err) (Just retry) (Just cell))
    }


updateRoster : (T.RosterOut -> T.RosterOut) -> Model -> Model
updateRoster f model =
    { model | roster = Maybe.map f model.roster }


upsert : { a | id : Int } -> List { a | id : Int } -> List { a | id : Int }
upsert item items =
    if List.any (\i -> i.id == item.id) items then
        List.map
            (\i ->
                if i.id == item.id then
                    item

                else
                    i
            )
            items

    else
        items ++ [ item ]


toggle : comparable -> Bool -> Set comparable -> Set comparable
toggle value shown hidden =
    if shown then
        Set.remove value hidden

    else
        Set.insert value hidden


{-| The week is the last part of the editor's URL, e.g. /roster/editor/next/2026-10-12/.
-}
weekFromPath : String -> Maybe Date
weekFromPath path =
    path
        |> String.split "/"
        |> List.filter (not << String.isEmpty)
        |> List.reverse
        |> List.head
        |> Maybe.andThen (Date.fromIsoString >> Result.toMaybe)



-- SUBSCRIPTIONS


subscriptions : Model -> Sub Msg
subscriptions model =
    Sub.batch
        [ onUrlChange UrlChanged
        , if model.publish /= Nothing then
            onEscape ClosePublish

          else if model.popover /= Nothing then
            onEscape ClosePopover

          else
            Sub.none
        ]


onEscape : Msg -> Sub Msg
onEscape msg =
    Browser.Events.onKeyDown
        (Decode.field "key" Decode.string
            |> Decode.andThen
                (\key ->
                    if key == "Escape" then
                        Decode.succeed msg

                    else
                        Decode.fail key
                )
        )



-- ROSTER QUERIES


nullable : Nullable a -> Maybe a
nullable value =
    case value of
        Present a ->
            Just a

        Null ->
            Nothing


day : Date -> Int
day =
    Date.toRataDie


cellShifts : T.RosterOut -> Cell -> List T.ShiftOut
cellShifts roster ( registrar, d ) =
    List.filter (\s -> nullable s.registrar == Just registrar && day s.date == d) roster.shifts


cellLeaves : T.RosterOut -> Cell -> List T.LeaveOut
cellLeaves roster ( registrar, d ) =
    List.filter (\l -> l.registrar == registrar && day l.date == d) roster.leaves


registrarName : Model -> Int -> String
registrarName model registrarId =
    model.roster
        |> Maybe.map .registrars
        |> Maybe.withDefault []
        |> List.filter (\r -> r.id == registrarId)
        |> List.head
        |> Maybe.map .username
        |> Maybe.withDefault "this registrar"


describeCell : Model -> Cell -> String
describeCell model ( registrar, d ) =
    registrarName model registrar ++ " on " ++ dayDate (Date.fromRataDie d)


choiceFor : List Choice -> String -> Choice
choiceFor choices value =
    choices
        |> List.filter (\c -> c.value == value)
        |> List.head
        |> Maybe.withDefault { value = value, label = value, short = value, key = "" }


shiftChoice : Model -> T.ShiftType -> Choice
shiftChoice model shiftType =
    choiceFor model.flags.shiftTypes (T.shiftTypeToString shiftType)


leaveChoice : Model -> T.LeaveType -> Choice
leaveChoice model leaveType =
    choiceFor model.flags.leaveTypes (T.leaveTypeToString leaveType)


{-| The page's shift types, in its order, paired with the generated enum.
-}
shiftChoices : Model -> List ( T.ShiftType, Choice )
shiftChoices model =
    List.filterMap (\c -> T.shiftTypeFromString c.value |> Maybe.map (\t -> ( t, c ))) model.flags.shiftTypes


shiftLabel : Model -> T.ShiftType -> String
shiftLabel model shiftType =
    String.toLower (shiftChoice model shiftType).label


shiftClass : T.ShiftType -> String
shiftClass shiftType =
    "is-" ++ String.toLower (T.shiftTypeToString shiftType)


isDuty : T.ShiftType -> Bool
isDuty shiftType =
    shiftType /= T.ShiftType__RDO && shiftType /= T.ShiftType__SLEEP


{-| Leave that takes the registrar off the roster: not cancelled or declined.
-}
isActiveLeave : T.LeaveOut -> Bool
isActiveLeave leave =
    case leaveState leave of
        Cancelled ->
            False

        Declined ->
            False

        _ ->
            True


type Cover
    = Covered
    | Posted
    | Missing


{-| Whether a shift the department needs every day is filled, posted but not given to anyone, or missing.
-}
coverFor : T.RosterOut -> Date -> String -> Cover
coverFor roster date shiftType =
    let
        onDay =
            List.filter (\s -> s.date == date && T.shiftTypeToString s.type_ == shiftType) roster.shifts
    in
    if List.any (\s -> s.registrar /= Null) onDay then
        Covered

    else if List.isEmpty onDay then
        Missing

    else
        Posted


type alias Window =
    { today : Date
    , holidays : Dict Int String
    , published : Maybe T.PublishedRange
    , dates : List Date
    }


isPublished : Window -> Date -> Bool
isPublished window date =
    case window.published of
        Just range ->
            Date.isBetween range.start range.end date

        Nothing ->
            False



-- VIEW


view : Model -> Html Msg
view model =
    div [ class "roster-editor" ]
        [ viewToolbar model
        , case model.roster of
            Just roster ->
                viewGrid model roster

            Nothing ->
                div [ class "re-empty" ]
                    [ if model.loading then
                        text "Loading the roster…"

                      else
                        text ""
                    ]
        , viewPopover model
        , viewPublish model
        , viewFailure model.failure
        , div [ class "visually-hidden", attribute "aria-live" "polite", attribute "role" "status" ] [ text model.announcement ]
        ]


viewToolbar : Model -> Html Msg
viewToolbar model =
    let
        hiddenCount =
            Set.size model.hiddenShiftTypes + Set.size model.hiddenLeaveTypes
    in
    div ([ class "re-toolbar" ] ++ inertWhen (model.publish /= Nothing))
        [ h1 [ class "re-title" ] [ text "Roster" ]
        , case model.roster of
            Just roster ->
                div [ class "re-nav" ]
                    [ div [ class "input-group input-group-sm flex-nowrap w-auto" ]
                        [ button [ type_ "button", class "btn btn-outline-secondary", attribute "aria-label" "Previous week", title "Previous week", onClick (GoToWeek roster.prev) ]
                            [ i [ class "bi bi-chevron-left", attribute "aria-hidden" "true" ] [] ]
                        , input
                            [ type_ "date"
                            , class "form-control re-week-input"
                            , value (Date.toIsoString model.week)
                            , attribute "aria-label" "Go to the week of"
                            , on "change" (Decode.map PickWeek targetValue)
                            ]
                            []
                        , button [ type_ "button", class "btn btn-outline-secondary", attribute "aria-label" "Next week", title "Next week", onClick (GoToWeek roster.next) ]
                            [ i [ class "bi bi-chevron-right", attribute "aria-hidden" "true" ] [] ]
                        ]
                    , button [ type_ "button", class "btn btn-sm btn-outline-secondary", onClick (GoToWeek roster.today) ] [ text "Today" ]
                    , span [ class "re-window" ] [ text (windowLabel roster.dates) ]
                    ]

            Nothing ->
                text ""
        , div [ class "re-tools" ]
            [ if model.loading then
                span [ class "re-loading" ] [ span [ class "spinner-border spinner-border-sm", attribute "aria-hidden" "true" ] [], text "Loading" ]

              else
                text ""
            , if hiddenCount > 0 then
                span [ class "re-hidden-note" ]
                    [ text (hiddenSummary model)
                    , button [ type_ "button", class "btn btn-link btn-sm p-0 align-baseline", onClick ShowAllTypes ] [ text "Show all" ]
                    ]

              else
                text ""
            , button
                [ type_ "button"
                , id "filters-button"
                , class "btn btn-sm btn-outline-secondary"
                , attribute "aria-haspopup" "dialog"
                , attribute "aria-expanded" (boolString (isFilters model.popover))
                , onClick (Open ForFilters "filters-button")
                ]
                [ i [ class "bi bi-funnel me-1", attribute "aria-hidden" "true" ] []
                , text "Filter"
                , if hiddenCount > 0 then
                    span [ class "badge text-bg-secondary ms-1" ] [ text (String.fromInt hiddenCount ++ " off") ]

                  else
                    text ""
                ]
            , button
                [ type_ "button"
                , id "key-button"
                , class "btn btn-sm btn-outline-secondary"
                , attribute "aria-haspopup" "dialog"
                , attribute "aria-expanded" (boolString (isKey model.popover))
                , onClick (Open ForKey "key-button")
                ]
                [ i [ class "bi bi-info-circle me-1", attribute "aria-hidden" "true" ] [], text "Key" ]
            , viewPublishedStatus model.roster
            , button [ type_ "button", id "publish-button", class "btn btn-sm btn-primary", onClick OpenPublish ]
                [ i [ class "bi bi-send me-1", attribute "aria-hidden" "true" ] [], text "Publish…" ]
            ]
        ]


viewPublishedStatus : Maybe T.RosterOut -> Html Msg
viewPublishedStatus roster =
    case roster |> Maybe.map (.published >> nullable) of
        Just (Just range) ->
            span [ class "re-published" ] [ text ("Published to " ++ dayDate range.end) ]

        Just Nothing ->
            span [ class "re-published is-none" ] [ text "Nothing published" ]

        Nothing ->
            text ""


hiddenSummary : Model -> String
hiddenSummary model =
    case model.roster of
        Just roster ->
            let
                shifts =
                    List.length (List.filter (\s -> Set.member (T.shiftTypeToString s.type_) model.hiddenShiftTypes) roster.shifts)

                leaves =
                    List.length (List.filter (\l -> Set.member (T.leaveTypeToString l.type_) model.hiddenLeaveTypes) roster.leaves)
            in
            "Hiding " ++ plural shifts "shift" "shifts" ++ " and " ++ String.fromInt leaves ++ " leave · "

        Nothing ->
            ""


viewGrid : Model -> T.RosterOut -> Html Msg
viewGrid model roster =
    let
        window =
            { today = roster.today
            , holidays = Dict.fromList (List.map (\h -> ( day h.date, h.name )) roster.holidays)
            , published = nullable roster.published
            , dates = roster.dates
            }

        cursor =
            case model.cursor of
                Just c ->
                    Just c

                Nothing ->
                    Maybe.map2 (\r d -> ( r.id, day d )) (List.head roster.registrars) (List.head roster.dates)
    in
    div
        ([ class "re-scroll"
         , classList [ ( "is-stale", model.loading ) ]
         , attribute "aria-busy" (boolString model.loading)
         ]
            ++ inertWhen (model.publish /= Nothing)
        )
        [ if List.isEmpty roster.registrars then
            p [ class "re-empty" ] [ text "No registrars are on the roster in these three weeks." ]

          else
            table
                [ class "re-grid"
                , attribute "role" "grid"
                , attribute "aria-label" ("Roster, " ++ windowLabel roster.dates)
                , preventDefaultOn "keydown" (gridKeyDecoder model)
                ]
                [ thead []
                    [ tr [ class "re-head" ]
                        (th [ scope "col", class "re-corner" ] [ text "Registrar" ]
                            :: List.indexedMap (viewDateHeader window) roster.dates
                        )
                    , tr [ class "re-cover" ]
                        (th [ scope "row", class "re-corner re-rowlabel" ] [ text "Cover" ]
                            :: List.indexedMap (viewCover model roster window) roster.dates
                        )
                    ]
                , tbody [] (List.map (viewRow model roster window cursor) roster.registrars)
                , tfoot []
                    [ tr []
                        (th [ scope "row", class "re-corner re-rowlabel" ] [ text "On leave" ]
                            :: List.indexedMap (viewLeaveCount roster window) roster.dates
                        )
                    ]
                ]
        ]


gridKeyDecoder : Model -> Decoder ( Msg, Bool )
gridKeyDecoder model =
    Decode.map4 (\key ctrl meta alt -> ( key, ctrl || meta || alt ))
        (Decode.field "key" Decode.string)
        (Decode.field "ctrlKey" Decode.bool)
        (Decode.field "metaKey" Decode.bool)
        (Decode.field "altKey" Decode.bool)
        |> Decode.andThen
            (\( key, modified ) ->
                let
                    shortcut =
                        List.any (\c -> c.key /= "" && c.key == String.toLower key) model.flags.shiftTypes
                in
                if modified || model.popover /= Nothing then
                    Decode.fail "not ours"

                else if List.member key [ "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "Enter", " ", "Delete", "Backspace" ] || shortcut then
                    Decode.succeed ( GridKey key, True )

                else
                    Decode.fail "not ours"
            )


columnClasses : Window -> Int -> Date -> List ( String, Bool )
columnClasses window index date =
    let
        previous =
            List.drop (index - 1) window.dates |> List.head
    in
    [ ( "is-weekend", isWeekend date )
    , ( "is-holiday", Dict.member (day date) window.holidays )
    , ( "is-today", date == window.today )
    , ( "is-unpublished", not (isPublished window date) )
    , ( "is-week-start", index > 0 && Date.weekday date == Time.Mon )
    , ( "is-focus-week", index >= 7 && index < 14 )
    , ( "is-publish-edge"
      , case previous of
            Just prev ->
                index > 0 && isPublished window prev /= isPublished window date

            Nothing ->
                False
      )
    ]


viewDateHeader : Window -> Int -> Date -> Html Msg
viewDateHeader window index date =
    th [ scope "col", classList (( "re-date", True ) :: columnClasses window index date) ]
        [ span [ class "re-weekday" ] [ text (Date.format "EEE" date) ]
        , span [ class "re-daydate" ] [ text (dayMonth date) ]
        , if date == window.today then
            span [ class "re-tag re-tag--today" ] [ text "Today" ]

          else
            text ""
        , case Dict.get (day date) window.holidays of
            Just name ->
                span [ class "re-tag re-tag--holiday", title (name ++ " (stat day)") ] [ text name ]

            Nothing ->
                text ""
        , if not (isPublished window date) then
            span [ class "re-tag re-tag--unpublished" ] [ text "Unpublished" ]

          else
            text ""
        ]


viewCover : Model -> T.RosterOut -> Window -> Int -> Date -> Html Msg
viewCover model roster window index date =
    td [ classList (( "re-cover-cell", True ) :: columnClasses window index date) ]
        (List.map
            (\shiftType ->
                let
                    choice =
                        choiceFor model.flags.shiftTypes shiftType

                    ( state, icon, name ) =
                        case coverFor roster date shiftType of
                            Covered ->
                                ( "ok", "bi-check-lg", "covered" )

                            Posted ->
                                ( "open", "bi-circle", "posted, not yet given to anyone" )

                            Missing ->
                                ( "gap", "bi-exclamation-triangle-fill", "missing" )
                in
                span [ class ("re-coverchip is-" ++ state), title (choice.label ++ " " ++ name) ]
                    [ i [ class ("bi " ++ icon), attribute "aria-hidden" "true" ] []
                    , text choice.short
                    , span [ class "visually-hidden" ] [ text (" " ++ name) ]
                    ]
            )
            model.flags.cover
        )


viewRow : Model -> T.RosterOut -> Window -> Maybe Cell -> T.RegistrarOut -> Html Msg
viewRow model roster window cursor registrar =
    tr []
        (th [ scope "row", class "re-name" ]
            [ span [ class "re-username" ] [ text registrar.username ]
            , case nullable registrar.year of
                Just year ->
                    span [ class "re-year" ]
                        [ text ("Y" ++ String.fromInt year)
                        , span [ class "visually-hidden" ] [ text (", year " ++ String.fromInt year) ]
                        ]

                Nothing ->
                    text ""
            ]
            :: List.indexedMap (\index date -> viewCell model roster window cursor registrar index date) roster.dates
        )


viewCell : Model -> T.RosterOut -> Window -> Maybe Cell -> T.RegistrarOut -> Int -> Date -> Html Msg
viewCell model roster window cursor registrar index date =
    let
        cell =
            ( registrar.id, day date )

        shifts =
            cellShifts roster cell

        leaves =
            cellLeaves roster cell

        clash =
            List.any (.type_ >> isDuty) shifts && List.any isActiveLeave leaves

        visibleShifts =
            List.filter (\s -> not (Set.member (T.shiftTypeToString s.type_) model.hiddenShiftTypes)) shifts

        visibleLeaves =
            List.filter (\l -> not (Set.member (T.leaveTypeToString l.type_) model.hiddenLeaveTypes)) leaves

        saving =
            Set.member cell model.saving
    in
    td
        [ id (cellId cell)
        , attribute "role" "gridcell"
        , tabindex
            (if cursor == Just cell then
                0

             else
                -1
            )
        , classList
            ([ ( "re-cell", True )
             , ( "is-saving", saving )
             , ( "has-error", Maybe.andThen .cell model.failure == Just cell )
             , ( "has-clash", clash )
             , ( "is-open", isCellOpen cell model.popover )
             ]
                ++ columnClasses window index date
            )
        , attribute "aria-busy" (boolString saving)
        , attribute "aria-haspopup" "dialog"
        , onFocus (Focused cell)
        , onClick (Open (ForCell cell Nothing) (cellId cell))
        ]
        (List.map (viewShiftChip model) visibleShifts
            ++ List.map (viewLeaveChip model) visibleLeaves
            ++ (if clash then
                    [ span [ class "re-clash", title "A shift clashes with leave" ]
                        [ i [ class "bi bi-exclamation-triangle-fill", attribute "aria-hidden" "true" ] []
                        , span [ class "visually-hidden" ] [ text "Clash: a shift on a day of leave" ]
                        ]
                    ]

                else
                    []
               )
            ++ (if List.isEmpty visibleShifts && List.isEmpty visibleLeaves then
                    [ span [ class "re-add", attribute "aria-hidden" "true" ] [ text "+" ]
                    , span [ class "visually-hidden" ] [ text "Empty" ]
                    ]

                else
                    []
               )
        )


viewShiftChip : Model -> T.ShiftOut -> Html Msg
viewShiftChip model shift =
    let
        choice =
            shiftChoice model shift.type_
    in
    span [ class ("re-chip re-shift " ++ shiftClass shift.type_), title choice.label ]
        [ text choice.short
        , if shift.extra_duty then
            span [ class "re-extra" ]
                [ i [ class "bi bi-coin", attribute "aria-hidden" "true" ] []
                , span [ class "visually-hidden" ] [ text ", extra duty" ]
                ]

          else
            text ""
        ]


viewLeaveChip : Model -> T.LeaveOut -> Html Msg
viewLeaveChip model leave =
    let
        choice =
            leaveChoice model leave.type_

        state =
            leaveState leave
    in
    span [ class ("re-chip re-leave is-" ++ leaveStateClass state), title (choice.label ++ " leave" ++ portionLabel leave ++ ", " ++ leaveStateName state) ]
        [ i [ class ("bi " ++ leaveIcon state), attribute "aria-hidden" "true" ] []
        , text (portionPrefix leave ++ choice.short)
        , span [ class "visually-hidden" ] [ text (" leave, " ++ leaveStateName state) ]
        ]


viewLeaveCount : T.RosterOut -> Window -> Int -> Date -> Html Msg
viewLeaveCount roster window index date =
    let
        onDay =
            List.filter (\l -> l.date == date && isActiveLeave l) roster.leaves

        approved =
            List.length (List.filter (\l -> leaveState l == Approved) onDay)

        waiting =
            List.length onDay - approved
    in
    td [ classList (( "re-count", True ) :: columnClasses window index date) ]
        (if List.isEmpty onDay then
            [ span [ class "re-count-none", attribute "aria-hidden" "true" ] [ text "–" ]
            , span [ class "visually-hidden" ] [ text "No one on leave" ]
            ]

         else
            [ span [ class "re-count-approved", attribute "aria-hidden" "true" ] [ i [ class "bi bi-check-lg" ] [], text (String.fromInt approved) ]
            , span [ class "re-count-pending", attribute "aria-hidden" "true" ] [ i [ class "bi bi-hourglass-split" ] [], text (String.fromInt waiting) ]
            , span [ class "visually-hidden" ] [ text (String.fromInt approved ++ " approved, " ++ String.fromInt waiting ++ " waiting") ]
            ]
        )



-- POPOVERS


viewPopover : Model -> Html Msg
viewPopover model =
    case ( model.popover, model.roster ) of
        ( Just (CellMenu cell anchor confirm), Just roster ) ->
            popoverShell anchor 340 (describeCellLong model roster cell) (viewCellMenu model roster cell confirm)

        ( Just (FiltersMenu anchor), _ ) ->
            popoverShell anchor 300 "Show in the grid" (viewFilters model)

        ( Just (KeyMenu anchor), _ ) ->
            popoverShell anchor 360 "Key" (viewKey model)

        _ ->
            text ""


{-| A popover in a fixed layer, opening below its anchor, or above it when the anchor is low on screen.
Focus stays inside: the sentinels at either end send it back round.
-}
popoverShell : Anchor -> Float -> String -> List (Html Msg) -> Html Msg
popoverShell anchor width heading content =
    let
        left =
            clamp 8 (anchor.viewportWidth - width - 8) anchor.left

        below =
            (anchor.top + anchor.bottom) / 2 < anchor.viewportHeight / 2

        vertical =
            if below then
                [ style "top" (px (anchor.bottom + 4)), style "max-height" (px (anchor.viewportHeight - anchor.bottom - 16)) ]

            else
                [ style "bottom" (px (anchor.viewportHeight - anchor.top + 4)), style "max-height" (px (anchor.top - 16)) ]
    in
    div []
        [ div [ class "re-backdrop", onClick ClosePopover ] []
        , div
            ([ class "re-popover"
             , attribute "role" "dialog"
             , attribute "aria-modal" "true"
             , attribute "aria-labelledby" "popover-title"
             , style "left" (px left)
             , style "width" (px width)
             ]
                ++ vertical
            )
            [ span [ tabindex 0, onFocus (FocusId "popover-last") ] []
            , div [ class "re-popover-head" ]
                [ h2 [ id "popover-title", class "re-popover-title" ] [ text heading ]
                , button [ type_ "button", id "popover-first", class "btn-close", attribute "aria-label" "Close", onClick ClosePopover ] []
                ]
            , div [ class "re-popover-body" ] content
            , div [ class "re-popover-foot" ]
                [ button [ type_ "button", id "popover-last", class "btn btn-sm btn-outline-secondary", onClick ClosePopover ] [ text "Close" ] ]
            , span [ tabindex 0, onFocus (FocusId "popover-first") ] []
            ]
        ]


describeCellLong : Model -> T.RosterOut -> Cell -> String
describeCellLong model roster ( registrar, d ) =
    let
        holiday =
            roster.holidays |> List.filter (\h -> day h.date == d) |> List.head |> Maybe.map (\h -> " · " ++ h.name)
    in
    registrarName model registrar ++ " · " ++ dayDate (Date.fromRataDie d) ++ Maybe.withDefault "" holiday


viewCellMenu : Model -> T.RosterOut -> Cell -> Maybe Int -> List (Html Msg)
viewCellMenu model roster cell confirm =
    let
        shifts =
            cellShifts roster cell

        leaves =
            cellLeaves roster cell

        window =
            { today = roster.today, holidays = Dict.empty, published = nullable roster.published, dates = roster.dates }

        notes =
            (if not (isPublished window (Date.fromRataDie (Tuple.second cell))) then
                [ p [ class "re-note" ] [ i [ class "bi bi-eye-slash me-1", attribute "aria-hidden" "true" ] [], text "Not published yet: registrars can't see this day." ] ]

             else
                []
            )
                ++ (if List.any isActiveLeave leaves && List.any (.type_ >> isDuty) shifts then
                        [ p [ class "re-note is-warning" ]
                            [ i [ class "bi bi-exclamation-triangle-fill me-1", attribute "aria-hidden" "true" ] []
                            , text "Rostered on a day of leave. Move the shift or decline the leave."
                            ]
                        ]

                    else
                        []
                   )
    in
    notes
        ++ List.map (viewLeaveSection model cell) leaves
        ++ List.map (viewShiftSection model cell confirm) shifts
        ++ [ viewAddSection model cell shifts leaves ]


viewShiftSection : Model -> Cell -> Maybe Int -> T.ShiftOut -> Html Msg
viewShiftSection model cell confirm shift =
    section [ class "re-section" ]
        (h3 [ class "re-section-title" ]
            [ span [ class ("re-chip re-shift " ++ shiftClass shift.type_) ] [ text (shiftChoice model shift.type_).short ]
            , text ((shiftChoice model shift.type_).label ++ " shift")
            ]
            :: (if confirm == Just shift.id then
                    [ p [ class "mb-2" ]
                        [ text ("Delete " ++ registrarName model (Tuple.first cell) ++ "'s " ++ shiftLabel model shift.type_ ++ " on " ++ dayDate shift.date ++ "?") ]
                    , div [ class "d-flex gap-2" ]
                        [ button [ type_ "button", id "confirm-delete", class "btn btn-sm btn-danger", onClick (DeleteShift cell shift.id) ] [ text "Delete shift" ]
                        , button [ type_ "button", class "btn btn-sm btn-outline-secondary", onClick (Open (ForCell cell Nothing) (cellId cell)) ] [ text "Keep it" ]
                        ]
                    ]

                else
                    [ div [ class "re-label" ] [ text "Change to" ]
                    , div [ class "re-typegrid" ]
                        (List.map
                            (\( shiftType, choice ) ->
                                button
                                    [ type_ "button"
                                    , classList [ ( "btn btn-sm re-typebtn", True ), ( "is-current", shiftType == shift.type_ ) ]
                                    , disabled (shiftType == shift.type_)
                                    , attribute "aria-label" ("Change to " ++ choice.label)
                                    , onClick (ChangeShift cell shift.id { type_ = Just shiftType, extra_duty = Nothing })
                                    ]
                                    [ span [ class ("re-swatch " ++ shiftClass shiftType), attribute "aria-hidden" "true" ] []
                                    , text choice.label
                                    , kbd [] [ text (String.toUpper choice.key) ]
                                    ]
                            )
                            (shiftChoices model)
                        )
                    , div [ class "d-flex gap-2 mt-2" ]
                        [ button
                            [ type_ "button"
                            , class "btn btn-sm btn-outline-secondary"
                            , attribute "aria-pressed" (boolString shift.extra_duty)
                            , onClick (ChangeShift cell shift.id { type_ = Nothing, extra_duty = Just (not shift.extra_duty) })
                            ]
                            [ i [ class "bi bi-coin me-1", attribute "aria-hidden" "true" ] []
                            , text
                                (if shift.extra_duty then
                                    "Extra duty: on"

                                 else
                                    "Mark as extra duty"
                                )
                            ]
                        , button [ type_ "button", class "btn btn-sm btn-outline-danger ms-auto", onClick (AskDelete cell shift.id) ]
                            [ i [ class "bi bi-trash3 me-1", attribute "aria-hidden" "true" ] [], text "Delete…" ]
                        ]
                    ]
               )
        )


viewAddSection : Model -> Cell -> List T.ShiftOut -> List T.LeaveOut -> Html Msg
viewAddSection model cell shifts leaves =
    section [ class "re-section" ]
        [ h3 [ class "re-section-title" ]
            [ text
                (if List.isEmpty shifts then
                    "Add a shift"

                 else
                    "Add another shift"
                )
            ]
        , if List.any isActiveLeave leaves then
            p [ class "re-note is-warning" ] [ text "This registrar is on leave this day." ]

          else
            text ""
        , div [ class "re-typegrid" ]
            (List.map
                (\( shiftType, choice ) ->
                    button [ type_ "button", class "btn btn-sm re-typebtn", attribute "aria-label" ("Add " ++ choice.label), onClick (AddShift cell shiftType) ]
                        [ span [ class ("re-swatch " ++ shiftClass shiftType), attribute "aria-hidden" "true" ] []
                        , text choice.label
                        , kbd [] [ text (String.toUpper choice.key) ]
                        ]
                )
                (shiftChoices model)
            )
        ]


viewLeaveSection : Model -> Cell -> T.LeaveOut -> Html Msg
viewLeaveSection model cell leave =
    let
        choice =
            leaveChoice model leave.type_

        state =
            leaveState leave
    in
    section [ class "re-section" ]
        [ h3 [ class "re-section-title" ]
            [ span [ class ("re-chip re-leave is-" ++ leaveStateClass state) ]
                [ i [ class ("bi " ++ leaveIcon state), attribute "aria-hidden" "true" ] [], text (portionPrefix leave ++ choice.short) ]
            , text (choice.label ++ " leave" ++ portionLabel leave)
            ]
        , p [ class "re-status" ] [ text (capitalise (leaveStateName state)) ]
        , if String.isEmpty leave.comment then
            text ""

          else
            p [ class "re-comment" ] [ text ("“" ++ leave.comment ++ "”") ]
        , approvalRow cell leave "Chief registrar" (\v -> { cancelled = Nothing, dot_approved = Nothing, reg_approved = Just v }) (nullable leave.reg_approved)
        , approvalRow cell leave "Director of Training" (\v -> { cancelled = Nothing, dot_approved = Just v, reg_approved = Nothing }) (nullable leave.dot_approved)
        , div [ class "mt-2" ]
            [ button
                [ type_ "button"
                , class "btn btn-sm btn-outline-secondary"
                , onClick (ChangeLeave cell leave.id { cancelled = Just (not leave.cancelled), dot_approved = Nothing, reg_approved = Nothing })
                ]
                [ text
                    (if leave.cancelled then
                        "Restore leave"

                     else
                        "Mark as cancelled"
                    )
                ]
            ]
        , p [ class "re-meta" ] [ text ("Requested " ++ dateTime model.zone leave.created ++ " · updated " ++ dateTime model.zone leave.last_edited) ]
        ]


approvalRow : Cell -> T.LeaveOut -> String -> (Nullable Bool -> T.LeavePatch) -> Maybe Bool -> Html Msg
approvalRow cell leave who toPatch current =
    let
        option value label variant =
            button
                [ type_ "button"
                , classList [ ( "btn btn-sm", True ), ( "btn-" ++ variant, current == value ), ( "btn-outline-" ++ variant, current /= value ) ]
                , attribute "aria-pressed" (boolString (current == value))
                , disabled leave.cancelled
                , onClick
                    (ChangeLeave cell
                        leave.id
                        (toPatch
                            (case value of
                                Just b ->
                                    Present b

                                Nothing ->
                                    Null
                            )
                        )
                    )
                ]
                [ text label ]
    in
    div [ class "re-approval" ]
        [ span [ class "re-label" ] [ text who ]
        , div [ class "btn-group btn-group-sm", attribute "role" "group", attribute "aria-label" (who ++ " approval") ]
            [ option (Just True) "Approve" "success"
            , option Nothing "Waiting" "secondary"
            , option (Just False) "Decline" "danger"
            ]
        ]


viewFilters : Model -> List (Html Msg)
viewFilters model =
    [ viewFilterGroup "Shifts" "shift-type" model.flags.shiftTypes model.hiddenShiftTypes ToggleShiftType
    , viewFilterGroup "Leave" "leave-type" model.flags.leaveTypes model.hiddenLeaveTypes ToggleLeaveType
    , button [ type_ "button", class "btn btn-sm btn-link px-0", onClick ShowAllTypes ] [ text "Show everything" ]
    ]


viewFilterGroup : String -> String -> List Choice -> Set String -> (String -> Bool -> Msg) -> Html Msg
viewFilterGroup heading idPrefix choices hidden toMsg =
    fieldset [ class "re-section" ]
        (Html.legend [ class "re-section-title" ] [ text heading ]
            :: List.map
                (\choice ->
                    let
                        inputId =
                            idPrefix ++ "-" ++ choice.value
                    in
                    div [ class "form-check" ]
                        [ input
                            [ type_ "checkbox"
                            , class "form-check-input"
                            , id inputId
                            , checked (not (Set.member choice.value hidden))
                            , onCheck (toMsg choice.value)
                            ]
                            []
                        , label [ class "form-check-label", for inputId ] [ text choice.label ]
                        ]
                )
                choices
        )


viewKey : Model -> List (Html Msg)
viewKey model =
    [ section [ class "re-section" ]
        [ h3 [ class "re-section-title" ] [ text "Shifts" ]
        , ul [ class "re-keylist" ]
            (List.map
                (\( shiftType, choice ) ->
                    li []
                        [ span [ class ("re-chip re-shift " ++ shiftClass shiftType) ] [ text choice.short ]
                        , text choice.label
                        , kbd [] [ text (String.toUpper choice.key) ]
                        ]
                )
                (shiftChoices model)
            )
        , p [ class "re-meta" ] [ i [ class "bi bi-coin me-1", attribute "aria-hidden" "true" ] [], text "marks an extra duty." ]
        ]
    , section [ class "re-section" ]
        [ h3 [ class "re-section-title" ] [ text "Leave" ]
        , ul [ class "re-keylist" ]
            (List.map
                (\state ->
                    li []
                        [ span [ class ("re-chip re-leave is-" ++ leaveStateClass state) ]
                            [ i [ class ("bi " ++ leaveIcon state), attribute "aria-hidden" "true" ] [], text "Annual" ]
                        , text (capitalise (leaveStateName state))
                        ]
                )
                [ Pending, PartlyApproved, Approved, Declined, Cancelled ]
            )
        ]
    , section [ class "re-section" ]
        [ h3 [ class "re-section-title" ] [ text "Days" ]
        , ul [ class "re-keylist" ]
            [ li [] [ span [ class "re-swatch is-weekend" ] [], text "Weekend" ]
            , li [] [ span [ class "re-swatch is-holiday" ] [], text "Public holiday (stat day)" ]
            , li [] [ span [ class "re-swatch is-unpublished" ] [], text "Not published: registrars can't see it" ]
            , li [] [ span [ class "re-coverchip is-ok" ] [ i [ class "bi bi-check-lg" ] [], text "Long" ], text "Cover: filled" ]
            , li [] [ span [ class "re-coverchip is-open" ] [ i [ class "bi bi-circle" ] [], text "Long" ], text "Cover: posted, not given out" ]
            , li [] [ span [ class "re-coverchip is-gap" ] [ i [ class "bi bi-exclamation-triangle-fill" ] [], text "Long" ], text "Cover: missing" ]
            , li []
                [ span [ class "re-count-approved" ] [ i [ class "bi bi-check-lg" ] [], text "2" ]
                , span [ class "re-count-pending" ] [ i [ class "bi bi-hourglass-split" ] [], text "1" ]
                , text "On leave: approved, waiting"
                ]
            ]
        ]
    , section [ class "re-section" ]
        [ h3 [ class "re-section-title" ] [ text "Keyboard" ]
        , ul [ class "re-keylist is-keys" ]
            [ li [] [ kbd [] [ text "← ↑ → ↓" ], text "Move between days and registrars" ]
            , li [] [ kbd [] [ text "Enter" ], text "Open the day" ]
            , li [] [ kbd [] [ text (String.join " " (List.map (\( _, c ) -> String.toUpper c.key) (shiftChoices model))) ], text "Add that shift, or change the one there" ]
            , li [] [ kbd [] [ text "Delete" ], text "Delete the day's shift (asks first)" ]
            , li [] [ kbd [] [ text "Esc" ], text "Close and go back to the day" ]
            ]
        ]
    ]



-- PUBLISH


viewPublish : Model -> Html Msg
viewPublish model =
    case model.publish of
        Just draft ->
            let
                valid =
                    draftRange draft /= Nothing

                hiding =
                    draft.preview |> Maybe.map (\p -> p.shifts_hidden + p.leave_hidden > 0) |> Maybe.withDefault False

                field fieldId labelText current toMsg =
                    div [ class "col" ]
                        [ label [ class "form-label", for fieldId ] [ text labelText ]
                        , input [ type_ "date", class "form-control", id fieldId, value current, onInput toMsg ] []
                        ]
            in
            div []
                [ div [ class "modal d-block", attribute "role" "dialog", attribute "aria-modal" "true", attribute "aria-labelledby" "publish-title" ]
                    [ div [ class "modal-dialog" ]
                        [ Html.form [ class "modal-content", onSubmit SavePublish ]
                            [ span [ tabindex 0, onFocus (FocusId "publish-cancel") ] []
                            , div [ class "modal-header" ]
                                [ h2 [ class "modal-title fs-5", id "publish-title" ] [ text "Publish the roster" ] ]
                            , div [ class "modal-body" ]
                                [ p [ class "text-body-secondary" ] [ text "Registrars see shifts and leave between these dates in the calendar and their phone calendar feeds." ]
                                , div [ class "row g-3" ]
                                    [ field "publish-start" "From" draft.start SetPublishStart
                                    , field "publish-end" "To" draft.end SetPublishEnd
                                    ]
                                , if valid then
                                    viewPreview draft

                                  else
                                    p [ class "re-note is-error mt-3 mb-0", attribute "role" "alert" ] [ text "The start must be on or before the end." ]
                                ]
                            , div [ class "modal-footer" ]
                                [ button [ type_ "button", id "publish-cancel", class "btn btn-outline-secondary", onClick ClosePublish ] [ text "Cancel" ]
                                , button
                                    [ type_ "submit"
                                    , classList [ ( "btn", True ), ( "btn-primary", not hiding ), ( "btn-danger", hiding ) ]
                                    , disabled (not valid || draft.saving)
                                    ]
                                    [ text (publishLabel draft) ]
                                ]
                            , span [ tabindex 0, onFocus (FocusId "publish-start") ] []
                            ]
                        ]
                    ]
                , div [ class "modal-backdrop show" ] []
                ]

        Nothing ->
            text ""


viewPreview : PublishDraft -> Html Msg
viewPreview draft =
    case draft.preview of
        Just preview ->
            div [ class "re-preview mt-3", attribute "aria-live" "polite" ]
                [ p [ class "mb-1" ]
                    [ text
                        (if preview.shifts_shown + preview.leave_shown == 0 then
                            "Registrars won't see anything new."

                         else
                            "Registrars will start seeing " ++ plural preview.shifts_shown "shift" "shifts" ++ " and " ++ String.fromInt preview.leave_shown ++ " leave."
                        )
                    ]
                , if preview.shifts_hidden + preview.leave_hidden > 0 then
                    p [ class "re-note is-warning mb-0" ]
                        [ i [ class "bi bi-exclamation-triangle-fill me-1", attribute "aria-hidden" "true" ] []
                        , text ("This hides " ++ plural preview.shifts_hidden "shift" "shifts" ++ " and " ++ String.fromInt preview.leave_hidden ++ " leave that registrars can see now.")
                        ]

                  else
                    text ""
                ]

        Nothing ->
            p [ class "re-meta mt-3 mb-0" ] [ text "Working out what changes…" ]


publishLabel : PublishDraft -> String
publishLabel draft =
    if draft.saving then
        "Publishing…"

    else
        case draft.preview of
            Just preview ->
                if preview.shifts_hidden + preview.leave_hidden > 0 then
                    "Publish and hide " ++ plural (preview.shifts_hidden + preview.leave_hidden) "item" "items"

                else
                    "Publish"

            Nothing ->
                "Publish"


viewFailure : Maybe Failure -> Html Msg
viewFailure failure =
    case failure of
        Just f ->
            div [ class "re-toast", attribute "role" "alert" ]
                [ i [ class "bi bi-exclamation-octagon-fill", attribute "aria-hidden" "true" ] []
                , span [ class "re-toast-text" ] [ text f.message ]
                , case f.retry of
                    Just retry ->
                        button [ type_ "button", class "btn btn-sm btn-light", onClick (Retry retry) ] [ text "Try again" ]

                    Nothing ->
                        text ""
                , button [ type_ "button", class "btn-close btn-close-white", attribute "aria-label" "Dismiss", onClick DismissFailure ] []
                ]

        Nothing ->
            text ""



-- LEAVE STATE


type LeaveState
    = Cancelled
    | Declined
    | Approved
    | PartlyApproved
    | Pending


leaveState : T.LeaveOut -> LeaveState
leaveState leave =
    let
        reg =
            nullable leave.reg_approved

        dot =
            nullable leave.dot_approved
    in
    if leave.cancelled then
        Cancelled

    else if reg == Just False || dot == Just False then
        Declined

    else if reg == Just True && dot == Just True then
        Approved

    else if reg == Just True || dot == Just True then
        PartlyApproved

    else
        Pending


leaveStateClass : LeaveState -> String
leaveStateClass state =
    case state of
        Cancelled ->
            "cancelled"

        Declined ->
            "declined"

        Approved ->
            "approved"

        PartlyApproved ->
            "partial"

        Pending ->
            "pending"


leaveIcon : LeaveState -> String
leaveIcon state =
    case state of
        Cancelled ->
            "bi-slash-circle"

        Declined ->
            "bi-x-lg"

        Approved ->
            "bi-check-lg"

        PartlyApproved ->
            "bi-hourglass-split"

        Pending ->
            "bi-question-lg"


leaveStateName : LeaveState -> String
leaveStateName state =
    case state of
        Cancelled ->
            "cancelled"

        Declined ->
            "declined"

        Approved ->
            "approved"

        PartlyApproved ->
            "approved by one, waiting on the other"

        Pending ->
            "waiting for approval"


{-| "PM " for a half day. It leads the chip so a narrow column cuts the leave type, not the half.
-}
portionPrefix : T.LeaveOut -> String
portionPrefix leave =
    if leave.portion == "ALL" then
        ""

    else
        leave.portion ++ " "


portionLabel : T.LeaveOut -> String
portionLabel leave =
    case leave.portion of
        "AM" ->
            " (morning)"

        "PM" ->
            " (afternoon)"

        _ ->
            " (all day)"



-- HELPERS


cellId : Cell -> String
cellId ( registrar, d ) =
    "cell-" ++ Date.toIsoString (Date.fromRataDie d) ++ "-" ++ String.fromInt registrar


isCellOpen : Cell -> Maybe Popover -> Bool
isCellOpen cell popover =
    case popover of
        Just (CellMenu c _ _) ->
            c == cell

        _ ->
            False


isFilters : Maybe Popover -> Bool
isFilters popover =
    case popover of
        Just (FiltersMenu _) ->
            True

        _ ->
            False


isKey : Maybe Popover -> Bool
isKey popover =
    case popover of
        Just (KeyMenu _) ->
            True

        _ ->
            False


{-| `inert` keeps a region out of reach while the publish dialog is open.
-}
inertWhen : Bool -> List (Attribute Msg)
inertWhen on =
    if on then
        [ attribute "inert" "" ]

    else
        []


boolString : Bool -> String
boolString b =
    if b then
        "true"

    else
        "false"


px : Float -> String
px value =
    String.fromFloat value ++ "px"


plural : Int -> String -> String -> String
plural n one many =
    String.fromInt n
        ++ " "
        ++ (if n == 1 then
                one

            else
                many
           )


capitalise : String -> String
capitalise s =
    String.toUpper (String.left 1 s) ++ String.dropLeft 1 s


isWeekend : Date -> Bool
isWeekend date =
    Date.weekdayNumber date >= 6


{-| "12 Oct"
-}
dayMonth : Date -> String
dayMonth =
    Date.format "d MMM"


{-| "Mon 12 Oct"
-}
dayDate : Date -> String
dayDate =
    Date.format "EEE d MMM"


{-| "Sun 25 Oct 2026"
-}
fullDate : Date -> String
fullDate =
    Date.format "EEE d MMM y"


windowLabel : List Date -> String
windowLabel dates =
    case ( List.head dates, List.head (List.reverse dates) ) of
        ( Just first, Just last ) ->
            dayMonth first ++ " – " ++ Date.format "d MMM y" last

        _ ->
            ""


{-| "7 Oct 2026, 16:21", in the browser's time zone.
-}
dateTime : Time.Zone -> Time.Posix -> String
dateTime zone posix =
    Date.format "d MMM y" (Date.fromPosix zone posix)
        ++ ", "
        ++ String.padLeft 2 '0' (String.fromInt (Time.toHour zone posix))
        ++ ":"
        ++ String.padLeft 2 '0' (String.fromInt (Time.toMinute zone posix))

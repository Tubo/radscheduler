port module Editor exposing (main)

{-| The roster editor: registrars by dates for three weeks, with shifts and leave in each cell.

The data comes from /api/editor/roster in one request, through the client generated from the API's
OpenAPI schema (`devenv shell -- elm:api`). The grid is the instrument: every cell is one keyboard stop
(arrow keys move, Enter opens it, a shift's key adds or changes that shift), and its menu opens in a
fixed layer over the grid, drawn only while open and never clipped by the scroll area.

The server checks the roster against the registrars' contracts after every change, and the editor marks
the cells each rule break touches. Edits save at once and can be undone (Ctrl+Z).

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


{-| A shift, leave or status type as the page describes it: stored value, full label, short label for the
grid, and the key that picks it (empty unless it is a shift). Labels live on the server so other
departments can differ.
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
    , statusTypes : List Choice
    , cover : CoverRules
    , workloadWeeks : Int
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
    , undo : List UndoStep
    , toast : Maybe Toast
    , toasts : Int
    , checksAsked : Int
    , checking : Bool
    , focusAfterLoad : Bool
    , wholeRequest : Bool
    , selectFrom : Maybe Cell
    , clipboard : Maybe Clip
    , batches : Dict Int Batch
    , batchCount : Int
    }


{-| Shift types copied from a block of cells, row by row; `Nothing` where a cell held no single shift.
-}
type alias Clip =
    List (List (Maybe T.ShiftType))


{-| Changes made together, saved one request each and undone as one step.
-}
type alias Batch =
    { label : String
    , remaining : Int
    , inverses : List Change
    , failed : Int
    }


{-| A key pressed in the grid, and the id of the element it was pressed on.
-}
type alias KeyPress =
    { key : String
    , shift : Bool
    , command : Bool
    , alt : Bool
    , target : String
    }


{-| A grid cell: registrar id and the day as a Rata Die number, so it can key sets and dicts.
-}
type alias Cell =
    ( Int, Int )


type Popover
    = CellMenu Cell Anchor Confirm
    | CoverMenu Date Anchor
    | FiltersMenu Anchor
    | KeyMenu Anchor
    | ProblemsMenu Anchor
    | ManyMenu Anchor String (List Change)


{-| What a cell's menu is asking about, if anything.
-}
type Confirm
    = NoConfirm
    | ConfirmDelete Int
    | ConfirmOnLeave Change
    | AddingAnother


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
    = ForCell Cell Confirm
    | ForCover Date
    | ForFilters
    | ForKey
    | ForProblems
    | ForMany String (List Change)


{-| A change to the roster. Each knows enough to describe itself and to be undone.
-}
type Change
    = AddShift Cell T.ShiftType Bool (Maybe Int) -- extra duty, and the deleted shift it brings back, if any
    | ChangeShift Cell T.ShiftOut T.ShiftPatch
    | DeleteShift Cell T.ShiftOut
    | ChangeLeaves Cell (List T.LeaveOut) LeaveChange


{-| A change to some days of leave. `Nothing` leaves a field as it is; a decision of `Just Nothing` puts it
back to waiting.
-}
type alias LeaveChange =
    { reg : Maybe (Maybe Bool)
    , dot : Maybe (Maybe Bool)
    , microster : Maybe Bool
    , cancelled : Maybe Bool
    }


noLeaveChange : LeaveChange
noLeaveChange =
    { reg = Nothing, dot = Nothing, microster = Nothing, cancelled = Nothing }


{-| Whether a change is the user's own or the undoing of one, which names the change it undoes.
-}
type Origin
    = Fresh
    | Undoing String
    | InBatch Int


type Outcome
    = ShiftSaved T.ShiftOut
    | ShiftGone T.ShiftOut
    | LeavesSaved (List T.LeaveOut)


type alias UndoStep =
    { label : String
    , changes : List Change
    }


type alias Toast =
    { id : Int
    , message : String
    , undoable : Bool
    }


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
    Decode.succeed Flags
        |> andMap (Decode.field "csrfToken" Decode.string)
        |> andMap (Decode.field "week" Decode.string)
        |> andMap (Decode.field "editorUrl" Decode.string)
        |> andMap (Decode.field "shiftTypes" (Decode.list choiceDecoder))
        |> andMap (Decode.field "leaveTypes" (Decode.list choiceDecoder))
        |> andMap (Decode.field "statusTypes" (Decode.list choiceDecoder))
        |> andMap (Decode.field "cover" coverRulesDecoder)
        |> andMap (Decode.field "workloadWeeks" Decode.int)
        |> andMap (optionalList "hiddenShiftTypes")
        |> andMap (optionalList "hiddenLeaveTypes")


andMap : Decoder a -> Decoder (a -> b) -> Decoder b
andMap =
    Decode.map2 (|>)


{-| What each day needs filled. Each requirement lists the shift types that meet it, e.g. a weekend day
needs a swing or a long day, and a night. Public holidays have their own rule.
-}
type alias CoverRules =
    { weekday : List (List String)
    , weekend : List (List String)
    , holiday : List (List String)
    }


coverRulesDecoder : Decoder CoverRules
coverRulesDecoder =
    Decode.map3 CoverRules
        (Decode.field "weekday" (Decode.list (Decode.list Decode.string)))
        (Decode.field "weekend" (Decode.list (Decode.list Decode.string)))
        (Decode.field "holiday" (Decode.list (Decode.list Decode.string)))


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
                    initialModel (Flags "" "" "" [] [] [] (CoverRules [] [] []) 0 [] []) (Date.fromRataDie 1)
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
    , undo = []
    , toast = Nothing
    , toasts = 0
    , checksAsked = 0
    , checking = False
    , focusAfterLoad = False
    , wholeRequest = True
    , selectFrom = Nothing
    , clipboard = Nothing
    , batches = Dict.empty
    , batchCount = 0
    }



-- REQUESTS


auth : Model -> { x_csrftoken : String }
auth model =
    { x_csrftoken = model.flags.csrfToken }


getRoster : Model -> Date -> Cmd Msg
getRoster model week =
    Api.getRoster { authorization = auth model, toMsg = GotRoster week, params = { week = week } }


{-| Ask for the rule breaks and workload again after a change. Only the answer to the latest request is used.
-}
refreshChecks : ( Model, Cmd Msg ) -> ( Model, Cmd Msg )
refreshChecks ( model, cmd ) =
    let
        asked =
            model.checksAsked + 1
    in
    ( { model | checksAsked = asked, checking = True }
    , Cmd.batch [ cmd, Api.getChecks { authorization = auth model, toMsg = GotChecks asked, params = { week = model.week } } ]
    )


{-| Send a change to the server. Shift changes close the menu; leave decisions keep it open, so both
approvals can be given in one visit.
-}
save : Origin -> Change -> Model -> ( Model, Cmd Msg )
save origin change model =
    let
        done =
            Saved origin change

        authorization =
            auth model

        request =
            case change of
                AddShift ( registrar, d ) shiftType extra _ ->
                    Api.addShift
                        { authorization = authorization
                        , toMsg = Result.map ShiftSaved >> done
                        , body = { date = Date.fromRataDie d, registrar = registrar, type_ = shiftType, extra_duty = Just extra }
                        }

                ChangeShift _ shift patch ->
                    Api.changeShift { authorization = authorization, toMsg = Result.map ShiftSaved >> done, body = patch, params = { shift_id = shift.id } }

                DeleteShift _ shift ->
                    Api.deleteShift { authorization = authorization, toMsg = Result.map ShiftGone >> done, params = { shift_id = shift.id } }

                ChangeLeaves _ leaves leaveChange ->
                    Api.changeLeaves { authorization = authorization, toMsg = Result.map LeavesSaved >> done, body = leavesPatch (List.map .id leaves) leaveChange }

        saving =
            startSaving (changeCell change) model
    in
    case change of
        ChangeLeaves _ _ _ ->
            ( saving, request )

        _ ->
            closePopover saving |> withCmd request


leavesPatch : List Int -> LeaveChange -> T.LeavesPatch
leavesPatch ids change =
    let
        decision =
            Maybe.map
                (\d ->
                    case d of
                        Just b ->
                            Present b

                        Nothing ->
                            Null
                )
    in
    { ids = ids
    , reg_approved = decision change.reg
    , dot_approved = decision change.dot
    , microster = change.microster
    , cancelled = change.cancelled
    }


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
    | GotChecks Int (Result ApiError T.ChecksOut)
    | GotZone Time.Zone
    | GoToWeek Date
    | PickWeek String
    | Reload
    | UrlChanged String
    | ToggleShiftType String Bool
    | ToggleLeaveType String Bool
    | ShowAllTypes
    | Focused Cell
    | GridKey KeyPress
    | CellClick Cell Bool
    | SaveMany String (List Change)
    | Open PopoverTarget String
    | GotAnchor PopoverTarget (Result Dom.Error Dom.Element)
    | ClosePopover
    | Request Change
    | Save Origin Change
    | Saved Origin Change (Result ApiError Outcome)
    | AssignCover Change
    | AskDelete Cell Int
    | AddAnother Cell
    | SetWholeRequest Bool
    | GoToCell Cell
    | GoToCover Date
    | UndoLast
    | DismissToast Int
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
                        ( { model | roster = Just roster, loading = False, checking = False, focusAfterLoad = False, announcement = "Showing " ++ windowLabel roster.dates }
                        , case ( model.focusAfterLoad, model.cursor ) of
                            ( True, Just cell ) ->
                                focusSoon (cellId cell)

                            _ ->
                                Cmd.none
                        )

                    Err err ->
                        ( { model | loading = False, failure = Just (Failure ("Couldn't load the roster. " ++ apiError err) (Just Reload) Nothing) }
                        , Cmd.none
                        )

        GotChecks asked result ->
            if asked /= model.checksAsked then
                ( model, Cmd.none )

            else
                case result of
                    Ok checks ->
                        ( updateRoster (\r -> { r | checks = checks }) { model | checking = False }, Cmd.none )

                    Err _ ->
                        -- Keep the last checks; the next change asks again.
                        ( { model | checking = False }, Cmd.none )

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

        GridKey press ->
            case ( model.cursor, model.roster ) of
                ( Just cell, Just roster ) ->
                    gridKey press cell roster model

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
                    let
                        sameCell =
                            case model.popover of
                                Just (CellMenu c _ _) ->
                                    c == cell

                                _ ->
                                    False
                    in
                    ( { model
                        | popover = Just (CellMenu cell anchor confirm)
                        , cursor = Just cell
                        , wholeRequest = sameCell && model.wholeRequest || not sameCell
                      }
                    , focusSoon
                        (case confirm of
                            NoConfirm ->
                                "popover-title"

                            AddingAnother ->
                                "add-first"

                            _ ->
                                "confirm-action"
                        )
                    )

                ForCover date ->
                    ( { model | popover = Just (CoverMenu date anchor) }, focusSoon "popover-title" )

                ForFilters ->
                    ( { model | popover = Just (FiltersMenu anchor) }, focusSoon "popover-title" )

                ForKey ->
                    ( { model | popover = Just (KeyMenu anchor) }, focusSoon "popover-title" )

                ForProblems ->
                    ( { model | popover = Just (ProblemsMenu anchor) }, focusSoon "popover-title" )

                ForMany question changes ->
                    ( { model | popover = Just (ManyMenu anchor question changes) }, focusSoon "confirm-action" )

        GotAnchor _ (Err _) ->
            ( model, Cmd.none )

        ClosePopover ->
            closePopover model

        Request change ->
            case model.roster of
                Just roster ->
                    if onLeaveFor roster change then
                        ( model, openCell (changeCell change) (ConfirmOnLeave change) )

                    else
                        save Fresh change model

                Nothing ->
                    ( model, Cmd.none )

        Save origin change ->
            save origin change model

        Saved (InBatch batchId) change result ->
            case Dict.get batchId model.batches of
                Just batch ->
                    batchStep batchId batch change result model

                Nothing ->
                    -- A retry after its batch finished stands on its own.
                    update (Saved Fresh change result) model

        Saved origin change (Ok outcome) ->
            let
                cell =
                    changeCell change

                label =
                    describeChange model change

                saved =
                    applyOutcome outcome model |> finishSaving cell label

                ( withUndo, message ) =
                    case origin of
                        Fresh ->
                            ( { saved | undo = List.take 50 ({ label = label, changes = inverse change outcome } :: saved.undo) }, label )

                        Undoing undone ->
                            ( { saved | undo = remapUndo change outcome saved.undo }, "Undone: " ++ undone )

                        InBatch _ ->
                            ( saved, label )
            in
            showToast message (origin == Fresh) withUndo |> refreshChecks

        Saved origin change (Err err) ->
            ( saveFailed (changeCell change) (Save origin change) err model, Cmd.none )

        CellClick cell extend ->
            if extend then
                ( { model | selectFrom = Just (Maybe.withDefault cell (orElse model.cursor model.selectFrom)), cursor = Just cell }
                    |> announceSelection
                , focus (cellId cell)
                )

            else
                update (Open (ForCell cell NoConfirm) (cellId cell)) { model | selectFrom = Nothing }

        SaveMany label changes ->
            let
                ( closed, cmd ) =
                    closePopover model
            in
            saveBatch label changes closed |> withCmd cmd

        AssignCover change ->
            let
                cell =
                    changeCell change
            in
            save Fresh change { model | popover = Nothing, cursor = Just cell }
                |> withCmd (focusSoon (cellId cell))

        AskDelete cell shiftId ->
            case model.popover of
                Just (CellMenu c anchor _) ->
                    ( { model | popover = Just (CellMenu c anchor (ConfirmDelete shiftId)) }, focusSoon "confirm-action" )

                _ ->
                    ( model, openCell cell (ConfirmDelete shiftId) )

        AddAnother cell ->
            case model.popover of
                Just (CellMenu c anchor _) ->
                    ( { model | popover = Just (CellMenu c anchor AddingAnother) }, focusSoon "add-first" )

                _ ->
                    ( model, openCell cell AddingAnother )

        SetWholeRequest whole ->
            ( { model | wholeRequest = whole }, Cmd.none )

        GoToCell cell ->
            ( { model | popover = Nothing, publish = Nothing, cursor = Just cell }
            , Process.sleep 30
                |> Task.andThen (\_ -> Dom.focus (cellId cell))
                |> Task.andThen (\_ -> Dom.getElement (cellId cell))
                |> Task.attempt (GotAnchor (ForCell cell NoConfirm))
            )

        GoToCover date ->
            ( { model | popover = Nothing, publish = Nothing }
            , Process.sleep 30
                |> Task.andThen (\_ -> Dom.focus (coverId date))
                |> Task.andThen (\_ -> Dom.getElement (coverId date))
                |> Task.attempt (GotAnchor (ForCover date))
            )

        UndoLast ->
            case model.undo of
                last :: rest ->
                    List.foldl
                        (\change ( m, cmds ) ->
                            let
                                ( next, cmd ) =
                                    save (Undoing last.label) change m
                            in
                            ( next, cmd :: cmds )
                        )
                        ( { model | undo = rest, toast = Nothing, announcement = "Undoing: " ++ last.label }, [] )
                        last.changes
                        |> Tuple.mapSecond Cmd.batch

                [] ->
                    showToast "Nothing to undo." False model

        DismissToast toastId ->
            if Maybe.map .id model.toast == Just toastId then
                ( { model | toast = Nothing }, Cmd.none )

            else
                ( model, Cmd.none )

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
                    if draft.saving || not (publishChanges model draft) then
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


{-| Arrow keys move, Home and End jump along the row, Page Up and Page Down go a week back or on, Enter or
Space opens the cell, a shift's key adds or changes that shift, Delete asks to delete the cell's shift, ] and
[ step through the problems, and ? opens the key. With Shift held, moving selects a block of cells: a shift's
key then sets them all, Delete clears them, and Ctrl+C copies them for Ctrl+V to paste elsewhere.
-}
gridKey : KeyPress -> Cell -> T.RosterOut -> Model -> ( Model, Cmd Msg )
gridKey press (( registrar, current ) as cell) roster model =
    let
        key =
            press.key

        rows =
            List.map .id roster.registrars

        days =
            List.map Date.toRataDie roster.dates

        go target =
            if press.shift then
                ( { model | cursor = Just target, selectFrom = Just (Maybe.withDefault cell model.selectFrom) } |> announceSelection
                , focus (cellId target)
                )

            else
                ( { model | cursor = Just target, selectFrom = Nothing }, focus (cellId target) )

        move rowStep colStep =
            go ( step rowStep registrar rows, step colStep current days )

        shifts =
            cellShifts roster cell

        selected =
            selectedCells model roster

        many =
            List.length selected > 1

        week target offset =
            update (GoToWeek target) { model | cursor = Just ( registrar, current + offset ), focusAfterLoad = True, selectFrom = Nothing }
    in
    if press.command then
        case String.toLower key of
            "c" ->
                copy roster model

            "v" ->
                paste roster model

            _ ->
                ( model, Cmd.none )

    else
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
                go ( registrar, List.head days |> Maybe.withDefault current )

            "End" ->
                go ( registrar, List.reverse days |> List.head |> Maybe.withDefault current )

            "PageUp" ->
                week roster.prev -7

            "PageDown" ->
                week roster.next 7

            "Escape" ->
                ( { model | selectFrom = Nothing, announcement = "Selection cleared." }, Cmd.none )

            "Enter" ->
                ( model, openCell cell NoConfirm )

            " " ->
                ( model, openCell cell NoConfirm )

            "Delete" ->
                if many then
                    deleteMany selected roster model

                else
                    deleteKey cell shifts model

            "Backspace" ->
                if many then
                    deleteMany selected roster model

                else
                    deleteKey cell shifts model

            "]" ->
                stepProblem 1 press.target roster model

            "[" ->
                stepProblem -1 press.target roster model

            "?" ->
                ( model, Task.attempt (GotAnchor ForKey) (Dom.getElement "key-button") )

            _ ->
                case List.filter (\( _, c ) -> c.key == String.toLower key) (shiftChoices model) of
                    ( shiftType, choice ) :: _ ->
                        if many then
                            assignMany shiftType choice selected roster model

                        else
                            case shifts of
                                [] ->
                                    update (Request (AddShift cell shiftType False Nothing)) model

                                [ shift ] ->
                                    if shift.type_ == shiftType then
                                        ( model, Cmd.none )

                                    else
                                        update (Request (ChangeShift cell shift { type_ = Just shiftType, extra_duty = Nothing })) model

                                _ ->
                                    ( model, openCell cell NoConfirm )

                    [] ->
                        ( model, Cmd.none )


{-| The change that gives `cell` the shift type, if it needs one. A day of leave or a day with two shifts is
left alone when changing many cells at once.
-}
assignChange : T.RosterOut -> T.ShiftType -> Cell -> Result () (Maybe Change)
assignChange roster shiftType cell =
    if isDuty shiftType && List.any isActiveLeave (cellLeaves roster cell) then
        Err ()

    else
        case cellShifts roster cell of
            [] ->
                Ok (Just (AddShift cell shiftType False Nothing))

            [ shift ] ->
                if shift.type_ == shiftType then
                    Ok Nothing

                else
                    Ok (Just (ChangeShift cell shift { type_ = Just shiftType, extra_duty = Nothing }))

            _ ->
                Err ()


{-| Changes for many cells, and how many were left alone.
-}
assignAll : T.RosterOut -> List ( Cell, T.ShiftType ) -> ( List Change, Int )
assignAll roster targets =
    List.foldr
        (\( cell, shiftType ) ( changes, skipped ) ->
            case assignChange roster shiftType cell of
                Ok (Just change) ->
                    ( change :: changes, skipped )

                Ok Nothing ->
                    ( changes, skipped )

                Err () ->
                    ( changes, skipped + 1 )
        )
        ( [], 0 )
        targets


skippedNote : Int -> String
skippedNote skipped =
    if skipped == 0 then
        ""

    else
        " (left " ++ plural skipped "day" "days" ++ " of leave or with two shifts as they were)"


assignMany : T.ShiftType -> Choice -> List Cell -> T.RosterOut -> Model -> ( Model, Cmd Msg )
assignMany shiftType choice cells roster model =
    let
        ( changes, skipped ) =
            assignAll roster (List.map (\cell -> ( cell, shiftType )) cells)
    in
    saveBatch ("Set " ++ plural (List.length changes) "cell" "cells" ++ " to " ++ lowerLabel choice.label ++ skippedNote skipped) changes model


deleteMany : List Cell -> T.RosterOut -> Model -> ( Model, Cmd Msg )
deleteMany cells roster model =
    let
        changes =
            List.concatMap (\cell -> List.map (DeleteShift cell) (cellShifts roster cell)) cells
    in
    case ( changes, model.cursor ) of
        ( [], _ ) ->
            showToast "No shifts in the selected cells." False model

        ( _, Just cursor ) ->
            ( model
            , Task.attempt
                (GotAnchor (ForMany ("Delete " ++ plural (List.length changes) "shift" "shifts" ++ " in the selected cells? You can undo it.") changes))
                (Dom.getElement (cellId cursor))
            )

        ( _, Nothing ) ->
            ( model, Cmd.none )


{-| Copy the selected block, or the cursor's cell, as shift types.
-}
copy : T.RosterOut -> Model -> ( Model, Cmd Msg )
copy roster model =
    let
        clip =
            selectedBlock model roster
                |> List.map
                    (List.map
                        (\cell ->
                            case cellShifts roster cell of
                                [ shift ] ->
                                    Just shift.type_

                                _ ->
                                    Nothing
                        )
                    )

        rows =
            List.length clip

        columns =
            List.head clip |> Maybe.map List.length |> Maybe.withDefault 0
    in
    if List.all (List.all ((==) Nothing)) clip then
        showToast "Nothing to copy: the selected cells have no single shift." False model

    else
        showToast
            ("Copied "
                ++ (if rows > 1 then
                        plural rows "row" "rows" ++ " × "

                    else
                        ""
                   )
                ++ plural columns "day" "days"
                ++ ". Move to where it goes and press Ctrl+V."
            )
            False
            { model | clipboard = Just clip }


{-| Paste the copied shifts with their top left at the selection's top left, or the cursor. Empty copied cells
leave what is there; days of leave and days with two shifts are left alone.
-}
paste : T.RosterOut -> Model -> ( Model, Cmd Msg )
paste roster model =
    case ( model.clipboard, List.head (selectedBlock model roster) |> Maybe.andThen List.head ) of
        ( Just clip, Just ( top, left ) ) ->
            let
                rows =
                    List.map .id roster.registrars |> List.drop (indexOf top (List.map .id roster.registrars))

                lastDay =
                    List.reverse roster.dates |> List.head |> Maybe.map day |> Maybe.withDefault left

                targets =
                    List.map2
                        (\registrar clipRow ->
                            List.indexedMap
                                (\offset shiftType ->
                                    Maybe.map (\t -> ( ( registrar, left + offset ), t )) shiftType
                                        |> Maybe.andThen
                                            (\target ->
                                                if Tuple.second (Tuple.first target) <= lastDay then
                                                    Just target

                                                else
                                                    Nothing
                                            )
                                )
                                clipRow
                                |> List.filterMap identity
                        )
                        rows
                        clip
                        |> List.concat

                ( changes, skipped ) =
                    assignAll roster targets
            in
            saveBatch ("Pasted " ++ plural (List.length changes) "shift" "shifts" ++ skippedNote skipped) changes model

        ( Nothing, _ ) ->
            showToast "Nothing copied yet: select cells and press Ctrl+C first." False model

        _ ->
            ( model, Cmd.none )


{-| Send several changes, saved as one step to undo.
-}
saveBatch : String -> List Change -> Model -> ( Model, Cmd Msg )
saveBatch label changes model =
    case changes of
        [] ->
            showToast "Nothing to change." False model

        _ ->
            let
                batchId =
                    model.batchCount + 1

                started =
                    { model
                        | batchCount = batchId
                        , batches = Dict.insert batchId { label = label, remaining = List.length changes, inverses = [], failed = 0 } model.batches
                        , selectFrom = Nothing
                    }
            in
            List.foldl
                (\change ( m, cmds ) ->
                    let
                        ( next, cmd ) =
                            save (InBatch batchId) change m
                    in
                    ( next, cmd :: cmds )
                )
                ( started, [] )
                changes
                |> Tuple.mapSecond Cmd.batch


{-| One change of a batch is back from the server. The last one makes the batch a single undo step.
-}
batchStep : Int -> Batch -> Change -> Result ApiError Outcome -> Model -> ( Model, Cmd Msg )
batchStep batchId batch change result model =
    let
        cell =
            changeCell change

        ( stepped, applied ) =
            case result of
                Ok outcome ->
                    ( { batch | remaining = batch.remaining - 1, inverses = batch.inverses ++ inverse change outcome }
                    , applyOutcome outcome model |> finishSaving cell batch.label
                    )

                Err err ->
                    ( { batch | remaining = batch.remaining - 1, failed = batch.failed + 1 }
                    , saveFailed cell (Save (InBatch batchId) change) err model
                    )
    in
    if stepped.remaining > 0 then
        ( { applied | batches = Dict.insert batchId stepped applied.batches }, Cmd.none )

    else
        let
            undoable =
                not (List.isEmpty stepped.inverses)

            finished =
                { applied
                    | batches = Dict.remove batchId applied.batches
                    , undo =
                        if undoable then
                            List.take 50 ({ label = stepped.label, changes = stepped.inverses } :: applied.undo)

                        else
                            applied.undo
                }
        in
        showToast
            (if stepped.failed > 0 then
                stepped.label ++ ", but " ++ plural stepped.failed "change" "changes" ++ " failed"

             else
                stepped.label
            )
            undoable
            finished
            |> refreshChecks


{-| The selected block, row by row: from where Shift-selection started to the cursor, or just the cursor.
-}
selectedBlock : Model -> T.RosterOut -> List (List Cell)
selectedBlock model roster =
    case model.cursor of
        Just (( cursorRow, cursorDay ) as cursor) ->
            let
                ( fromRow, fromDay ) =
                    Maybe.withDefault cursor model.selectFrom

                ids =
                    List.map .id roster.registrars

                ( a, b ) =
                    ( indexOf fromRow ids, indexOf cursorRow ids )

                rows =
                    ids |> List.drop (Basics.min a b) |> List.take (abs (a - b) + 1)

                days =
                    List.range (Basics.min fromDay cursorDay) (Basics.max fromDay cursorDay)
            in
            List.map (\r -> List.map (Tuple.pair r) days) rows

        Nothing ->
            []


selectedCells : Model -> T.RosterOut -> List Cell
selectedCells model roster =
    List.concat (selectedBlock model roster)


announceSelection : Model -> Model
announceSelection model =
    case model.roster of
        Just roster ->
            { model | announcement = plural (List.length (selectedCells model roster)) "cell" "cells" ++ " selected." }

        Nothing ->
            model


indexOf : a -> List a -> Int
indexOf item items =
    List.indexedMap Tuple.pair items |> List.filter (\( _, i ) -> i == item) |> List.head |> Maybe.map Tuple.first |> Maybe.withDefault 0


orElse : Maybe a -> Maybe a -> Maybe a
orElse first second =
    case first of
        Just _ ->
            first

        Nothing ->
            second


{-| Where a problem is in the grid: a cover gap in the strip, or the first cell a rule break marks.
-}
type Stop
    = AtCover Date String
    | AtCell Cell String


{-| The problems in grid order, by day and then down the rows, the cover strip first.
-}
problemStops : Model -> T.RosterOut -> List ( ( Int, Int ), Stop )
problemStops model roster =
    let
        window =
            windowOf model roster

        ids =
            List.map .id roster.registrars

        gaps =
            List.filterMap
                (\date ->
                    case coverGaps model roster window date of
                        [] ->
                            Nothing

                        needs ->
                            Just ( ( day date, -1 ), AtCover date (dayDate date ++ " needs " ++ String.join " and " (List.map (needsLabel model) needs)) )
                )
                roster.dates

        rules =
            List.filterMap
                (\v ->
                    markedCells roster v
                        |> List.head
                        |> Maybe.map
                            (\(( registrar, d ) as cell) ->
                                ( ( d, indexOf registrar ids )
                                , AtCell cell (registrarName model registrar ++ ", " ++ (nullable v.clause |> Maybe.withDefault "department rule") ++ ": " ++ v.message)
                                )
                            )
                )
                roster.checks.violations
    in
    List.sortBy Tuple.first (gaps ++ rules)


{-| Move to the next (or, going back, the previous) problem after the element the key was pressed on.
-}
stepProblem : Int -> String -> T.RosterOut -> Model -> ( Model, Cmd Msg )
stepProblem direction target roster model =
    let
        ids =
            List.map .id roster.registrars

        here =
            if String.startsWith "cell-" target then
                Maybe.map2 (\d r -> ( day d, indexOf r ids ))
                    (Date.fromIsoString (String.slice 5 15 target) |> Result.toMaybe)
                    (String.toInt (String.dropLeft 16 target))

            else if String.startsWith "cover-" target then
                Date.fromIsoString (String.slice 6 16 target) |> Result.toMaybe |> Maybe.map (\d -> ( day d, -1 ))

            else
                Nothing

        stops =
            if direction > 0 then
                problemStops model roster

            else
                List.reverse (problemStops model roster)

        after ( position, _ ) =
            case here of
                Just h ->
                    if direction > 0 then
                        position > h

                    else
                        position < h

                Nothing ->
                    True
    in
    case orElse (List.filter after stops |> List.head) (List.head stops) of
        Just ( _, AtCell cell message ) ->
            ( { model | cursor = Just cell, selectFrom = Nothing, announcement = message }, focus (cellId cell) )

        Just ( _, AtCover date message ) ->
            ( { model | announcement = message }, focus (coverId date) )

        Nothing ->
            showToast "No problems in these three weeks." False model


deleteKey : Cell -> List T.ShiftOut -> Model -> ( Model, Cmd Msg )
deleteKey cell shifts model =
    case shifts of
        [ shift ] ->
            ( model, openCell cell (ConfirmDelete shift.id) )

        [] ->
            ( model, Cmd.none )

        _ ->
            ( model, openCell cell NoConfirm )


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


openCell : Cell -> Confirm -> Cmd Msg
openCell cell confirm =
    Task.attempt (GotAnchor (ForCell cell confirm)) (Dom.getElement (cellId cell))


{-| Close any popover and give focus back to what opened it, once the grid behind it is no longer inert.
-}
closePopover : Model -> ( Model, Cmd Msg )
closePopover model =
    let
        closed =
            { model | popover = Nothing }
    in
    case model.popover of
        Just (CellMenu cell _ _) ->
            ( closed, focusSoon (cellId cell) )

        Just (CoverMenu date _) ->
            ( closed, focusSoon (coverId date) )

        Just (FiltersMenu _) ->
            ( closed, focusSoon "filters-button" )

        Just (KeyMenu _) ->
            ( closed, focusSoon "key-button" )

        Just (ProblemsMenu _) ->
            ( closed, focusSoon "problems-button" )

        Just (ManyMenu _ _ _) ->
            ( closed, Maybe.map (cellId >> focusSoon) model.cursor |> Maybe.withDefault Cmd.none )

        Nothing ->
            ( model, Cmd.none )


withCmd : Cmd Msg -> ( Model, Cmd Msg ) -> ( Model, Cmd Msg )
withCmd cmd ( model, other ) =
    ( model, Cmd.batch [ other, cmd ] )


focus : String -> Cmd Msg
focus elementId =
    Task.attempt (\_ -> NoOp) (Dom.focus elementId)


{-| Focus an element that the next render will draw, or free from `inert`.
-}
focusSoon : String -> Cmd Msg
focusSoon elementId =
    Process.sleep 30 |> Task.andThen (\_ -> Dom.focus elementId) |> Task.attempt (\_ -> NoOp)


load : Date -> Model -> ( Model, Cmd Msg )
load week model =
    ( { model | week = week, loading = True, popover = Nothing, selectFrom = Nothing, announcement = "Loading…", checksAsked = model.checksAsked + 1 }
    , getRoster model week
    )


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


{-| Whether publishing the draft would change the published range.
-}
publishChanges : Model -> PublishDraft -> Bool
publishChanges model draft =
    draftRange draft /= (model.roster |> Maybe.andThen (.published >> nullable))


startSaving : Cell -> Model -> Model
startSaving cell model =
    { model | saving = Set.insert cell model.saving, failure = Nothing, announcement = "Saving…" }


finishSaving : Cell -> String -> Model -> Model
finishSaving cell announcement model =
    { model | saving = Set.remove cell model.saving, announcement = announcement ++ "." }


saveFailed : Cell -> Msg -> ApiError -> Model -> Model
saveFailed cell retry err model =
    { model
        | saving = Set.remove cell model.saving
        , failure = Just (Failure ("Couldn't save the change for " ++ describeCell model cell ++ ". " ++ apiError err) (Just retry) (Just cell))
    }


showToast : String -> Bool -> Model -> ( Model, Cmd Msg )
showToast message undoable model =
    let
        toastId =
            model.toasts + 1
    in
    ( { model | toast = Just { id = toastId, message = message, undoable = undoable }, toasts = toastId }
    , Process.sleep 8000 |> Task.perform (\_ -> DismissToast toastId)
    )


updateRoster : (T.RosterOut -> T.RosterOut) -> Model -> Model
updateRoster f model =
    { model | roster = Maybe.map f model.roster }


applyOutcome : Outcome -> Model -> Model
applyOutcome outcome =
    case outcome of
        ShiftSaved shift ->
            updateRoster (\r -> { r | shifts = upsert shift r.shifts })

        ShiftGone shift ->
            updateRoster (\r -> { r | shifts = List.filter (\s -> s.id /= shift.id) r.shifts })

        LeavesSaved leaves ->
            updateRoster (\r -> { r | leaves = List.foldl upsert r.leaves leaves })


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



-- CHANGES AND UNDO


changeCell : Change -> Cell
changeCell change =
    case change of
        AddShift cell _ _ _ ->
            cell

        ChangeShift cell _ _ ->
            cell

        DeleteShift cell _ ->
            cell

        ChangeLeaves cell _ _ ->
            cell


{-| Whether a change would put a period of duty on a day the registrar is on leave, so it needs a yes first.
-}
onLeaveFor : T.RosterOut -> Change -> Bool
onLeaveFor roster change =
    let
        onLeave cell =
            List.any isActiveLeave (cellLeaves roster cell)
    in
    case change of
        AddShift cell shiftType _ _ ->
            isDuty shiftType && onLeave cell

        ChangeShift cell _ patch ->
            Maybe.map isDuty patch.type_ == Just True && onLeave cell

        _ ->
            False


{-| The changes that put things back as they were before `change`.
-}
inverse : Change -> Outcome -> List Change
inverse change outcome =
    case ( change, outcome ) of
        ( AddShift cell _ _ _, ShiftSaved added ) ->
            [ DeleteShift cell added ]

        ( ChangeShift cell before _, ShiftSaved after ) ->
            [ ChangeShift cell after { type_ = Just before.type_, extra_duty = Just before.extra_duty } ]

        ( DeleteShift cell deleted, _ ) ->
            [ AddShift cell deleted.type_ deleted.extra_duty (Just deleted.id) ]

        ( ChangeLeaves cell before leaveChange, _ ) ->
            -- Days that were in different states go back in separate requests.
            before
                |> List.map (\leave -> ( leaveBefore leaveChange leave, leave ))
                |> groupBy (Tuple.first >> leaveChangeKey)
                |> List.filterMap
                    (\group ->
                        List.head group |> Maybe.map (\( previous, _ ) -> ChangeLeaves cell (List.map Tuple.second group) previous)
                    )

        _ ->
            []


{-| The values `change` replaced on `leave`, for the fields it set.
-}
leaveBefore : LeaveChange -> T.LeaveOut -> LeaveChange
leaveBefore change leave =
    { reg = Maybe.map (\_ -> nullable leave.reg_approved) change.reg
    , dot = Maybe.map (\_ -> nullable leave.dot_approved) change.dot
    , microster = Maybe.map (\_ -> leave.microster) change.microster
    , cancelled = Maybe.map (\_ -> leave.cancelled) change.cancelled
    }


leaveChangeKey : LeaveChange -> String
leaveChangeKey change =
    let
        decision =
            Maybe.map (Maybe.map boolString >> Maybe.withDefault "waiting") >> Maybe.withDefault "-"
    in
    String.join "," [ decision change.reg, decision change.dot, Maybe.map boolString change.microster |> Maybe.withDefault "-", Maybe.map boolString change.cancelled |> Maybe.withDefault "-" ]


{-| Undoing a delete brings the shift back with a new id; later undo steps that name the old id follow it.
-}
remapUndo : Change -> Outcome -> List UndoStep -> List UndoStep
remapUndo change outcome steps =
    case ( change, outcome ) of
        ( AddShift _ _ _ (Just oldId), ShiftSaved restored ) ->
            let
                remap shift =
                    if shift.id == oldId then
                        { shift | id = restored.id }

                    else
                        shift

                remapChange c =
                    case c of
                        ChangeShift cell shift patch ->
                            ChangeShift cell (remap shift) patch

                        DeleteShift cell shift ->
                            DeleteShift cell (remap shift)

                        _ ->
                            c
            in
            List.map (\s -> { s | changes = List.map remapChange s.changes }) steps

        _ ->
            steps


{-| "Changed Kiri Tane's long day to a night on Wed 21 Oct"
-}
describeChange : Model -> Change -> String
describeChange model change =
    case change of
        AddShift ( registrar, d ) shiftType extra _ ->
            "Added "
                ++ withArticle (shiftLabel model shiftType)
                ++ (if extra then
                        " (extra duty)"

                    else
                        ""
                   )
                ++ " for "
                ++ registrarName model registrar
                ++ " on "
                ++ dayDate (Date.fromRataDie d)

        ChangeShift ( registrar, d ) before patch ->
            case ( patch.type_, patch.extra_duty ) of
                ( Just shiftType, _ ) ->
                    "Changed " ++ possessive (registrarName model registrar) ++ " " ++ shiftLabel model before.type_ ++ " to " ++ withArticle (shiftLabel model shiftType) ++ " on " ++ dayDate (Date.fromRataDie d)

                ( Nothing, Just True ) ->
                    "Marked " ++ possessive (registrarName model registrar) ++ " " ++ shiftLabel model before.type_ ++ " on " ++ dayDate (Date.fromRataDie d) ++ " as an extra duty"

                _ ->
                    "Made " ++ possessive (registrarName model registrar) ++ " " ++ shiftLabel model before.type_ ++ " on " ++ dayDate (Date.fromRataDie d) ++ " an ordinary shift"

        DeleteShift ( registrar, d ) deleted ->
            "Deleted " ++ possessive (registrarName model registrar) ++ " " ++ shiftLabel model deleted.type_ ++ " on " ++ dayDate (Date.fromRataDie d)

        ChangeLeaves ( registrar, _ ) leaves leaveChange ->
            let
                what =
                    possessive (registrarName model registrar)
                        ++ " "
                        ++ (List.head leaves |> Maybe.map (.type_ >> leaveChoice model >> .label >> String.toLower) |> Maybe.withDefault "")
                        ++ " leave"
                        ++ (case leaves of
                                [ leave ] ->
                                    " on " ++ dayDate leave.date

                                _ ->
                                    ", " ++ plural (List.length leaves) "day" "days"
                           )

                decided who decision =
                    case decision of
                        Just True ->
                            "Approved " ++ what ++ " for the " ++ who

                        Just False ->
                            "Declined " ++ what ++ " for the " ++ who

                        Nothing ->
                            "Put " ++ what ++ " back to waiting for the " ++ who
            in
            case ( ( leaveChange.reg, leaveChange.dot ), ( leaveChange.microster, leaveChange.cancelled ) ) of
                ( ( Just decision, _ ), _ ) ->
                    decided "chief registrar" decision

                ( ( _, Just decision ), _ ) ->
                    decided "Director of Training" decision

                ( _, ( Just True, _ ) ) ->
                    "Marked " ++ what ++ " as entered in Microster"

                ( _, ( Just False, _ ) ) ->
                    "Marked " ++ what ++ " as not in Microster"

                ( _, ( _, Just True ) ) ->
                    "Cancelled " ++ what

                _ ->
                    "Restored " ++ what


possessive : String -> String
possessive name =
    if String.endsWith "s" name then
        name ++ "'"

    else
        name ++ "'s"


withArticle : String -> String
withArticle word =
    let
        first =
            String.left 1 word

        acronym =
            String.toUpper word == word
    in
    if String.contains (String.toLower first) "aeiou" || (acronym && String.contains first "AEFHILMNORSX") then
        "an " ++ word

    else
        "a " ++ word


groupBy : (a -> comparable) -> List a -> List (List a)
groupBy key items =
    items
        |> List.foldl (\item groups -> Dict.update (key item) (\g -> Just (Maybe.withDefault [] g ++ [ item ])) groups) Dict.empty
        |> Dict.values



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
            Browser.Events.onKeyDown undoKey
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


{-| Ctrl+Z (Cmd+Z on a Mac) undoes the last change, unless the focus is in a text field.
-}
undoKey : Decoder Msg
undoKey =
    Decode.map4 (\key ctrl meta shift -> ( String.toLower key, ctrl || meta, shift ))
        (Decode.field "key" Decode.string)
        (Decode.field "ctrlKey" Decode.bool)
        (Decode.field "metaKey" Decode.bool)
        (Decode.field "shiftKey" Decode.bool)
        |> Decode.andThen
            (\( key, command, shift ) ->
                if key == "z" && command && not shift then
                    inTextField
                        |> Decode.andThen
                            (\typing ->
                                if typing then
                                    Decode.fail "typing"

                                else
                                    Decode.succeed UndoLast
                            )

                else
                    Decode.fail "not ours"
            )


inTextField : Decoder Bool
inTextField =
    Decode.oneOf [ Decode.at [ "target", "tagName" ] Decode.string, Decode.succeed "" ]
        |> Decode.map (\tag -> tag == "INPUT" || tag == "TEXTAREA" || tag == "SELECT")



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


findRegistrar : Model -> Int -> Maybe T.RegistrarOut
findRegistrar model registrarId =
    model.roster
        |> Maybe.map .registrars
        |> Maybe.withDefault []
        |> List.filter (\r -> r.id == registrarId)
        |> List.head


registrarName : Model -> Int -> String
registrarName model registrarId =
    findRegistrar model registrarId |> Maybe.map .name |> Maybe.withDefault "this registrar"


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


statusChoice : Model -> T.StatusType -> Choice
statusChoice model statusType =
    choiceFor model.flags.statusTypes (T.statusTypeToString statusType)


{-| The page's shift types, in its order, paired with the generated enum.
-}
shiftChoices : Model -> List ( T.ShiftType, Choice )
shiftChoices model =
    List.filterMap (\c -> T.shiftTypeFromString c.value |> Maybe.map (\t -> ( t, c ))) model.flags.shiftTypes


{-| "long day", "night", "RDO": lower case, except for an acronym.
-}
shiftLabel : Model -> T.ShiftType -> String
shiftLabel model shiftType =
    lowerLabel (shiftChoice model shiftType).label


lowerLabel : String -> String
lowerLabel label =
    if String.toUpper label == label then
        label

    else
        String.toLower label


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


{-| The other days of the leave request `leave` belongs to, in the three weeks shown: the same registrar,
type and half of the day, asked for together, on working days with only weekends and holidays between them.
-}
leaveRequest : T.RosterOut -> T.LeaveOut -> List T.LeaveOut
leaveRequest roster leave =
    let
        holidays =
            Set.fromList (List.map (.date >> day) roster.holidays)

        together other =
            other.registrar
                == leave.registrar
                && other.type_
                == leave.type_
                && other.portion
                == leave.portion
                && abs (Time.posixToMillis other.created - Time.posixToMillis leave.created)
                < 120000

        offBetween a b =
            List.range (day a + 1) (day b - 1)
                |> List.all (\d -> Set.member d holidays || isWeekend (Date.fromRataDie d))

        runs =
            roster.leaves
                |> List.filter together
                |> List.sortBy (.date >> day)
                |> List.foldl
                    (\l acc ->
                        case acc of
                            (last :: run) :: rest ->
                                if offBetween last.date l.date then
                                    (l :: last :: run) :: rest

                                else
                                    [ l ] :: acc

                            [] ->
                                [ [ l ] ]

                            [] :: rest ->
                                [ l ] :: rest
                    )
                    []
    in
    runs
        |> List.filter (List.any (\l -> l.id == leave.id))
        |> List.head
        |> Maybe.map List.reverse
        |> Maybe.withDefault [ leave ]


{-| How a day's cover requirement stands, naming the shift type that fills it.
-}
type Cover
    = Covered String
    | Posted String
    | Missing


{-| Whether one of the shift types that meet a requirement is filled, posted but not given to anyone, or missing.
-}
coverFor : T.RosterOut -> Date -> List String -> Cover
coverFor roster date alternatives =
    let
        onDay =
            List.filter (\s -> s.date == date && List.member (T.shiftTypeToString s.type_) alternatives) roster.shifts
    in
    case ( List.filter (\s -> s.registrar /= Null) onDay, onDay ) of
        ( filled :: _, _ ) ->
            Covered (T.shiftTypeToString filled.type_)

        ( [], posted :: _ ) ->
            Posted (T.shiftTypeToString posted.type_)

        ( [], [] ) ->
            Missing


coverRule : Model -> Window -> Date -> List (List String)
coverRule model window date =
    if Dict.member (day date) window.holidays then
        model.flags.cover.holiday

    else if isWeekend date then
        model.flags.cover.weekend

    else
        model.flags.cover.weekday


{-| The requirements nobody is rostered or posted for on a day.
-}
coverGaps : Model -> T.RosterOut -> Window -> Date -> List (List String)
coverGaps model roster window date =
    List.filter (\alternatives -> coverFor roster date alternatives == Missing) (coverRule model window date)


{-| "a swing day", "a swing day or long day"
-}
needsLabel : Model -> List String -> String
needsLabel model alternatives =
    case List.map (choiceFor model.flags.shiftTypes >> .label >> lowerLabel) alternatives of
        first :: rest ->
            String.join " or " (withArticle first :: rest)

        [] ->
            ""


type alias Window =
    { today : Date
    , holidays : Dict Int String
    , published : Maybe T.PublishedRange
    , dates : List Date
    }


{-| The days shown. While the publish dialog is open, the published range is the one being drafted.
-}
windowOf : Model -> T.RosterOut -> Window
windowOf model roster =
    { today = roster.today
    , holidays = Dict.fromList (List.map (\h -> ( day h.date, h.name )) roster.holidays)
    , published =
        case model.publish |> Maybe.andThen draftRange of
            Just draft ->
                Just draft

            Nothing ->
                nullable roster.published
    , dates = roster.dates
    }


isPublished : Window -> Date -> Bool
isPublished window date =
    case window.published of
        Just range ->
            Date.isBetween range.start range.end date

        Nothing ->
            False


{-| The checks, indexed for drawing the grid: rule breaks by cell, statuses by registrar, load by registrar.
-}
type alias Checks =
    { violations : Dict Cell (List T.ViolationOut)
    , statuses : Dict Int (List T.StatusOut)
    , load : Dict Int Float
    , maxLoad : Float
    , selected : Set Cell
    }


{-| The cells a rule break is marked on. A break over a stretch of days (say, too many hours in a week) is
marked where something is rostered, since that is what can move; one about empty days (no rest after nights)
marks those days.
-}
markedCells : T.RosterOut -> T.ViolationOut -> List Cell
markedCells roster violation =
    let
        shown =
            Set.fromList (List.map day roster.dates)

        occupied =
            Set.fromList
                (List.filterMap (\s -> nullable s.registrar |> Maybe.map (\r -> ( r, day s.date ))) roster.shifts
                    ++ List.map (\l -> ( l.registrar, day l.date )) roster.leaves
                )

        cells =
            List.filter (\d -> Set.member (day d) shown) violation.dates |> List.map (\d -> ( violation.registrar, day d ))

        busy =
            List.filter (\c -> Set.member c occupied) cells
    in
    if List.isEmpty busy then
        cells

    else
        busy


checksOf : T.RosterOut -> Checks
checksOf roster =
    let
        add key item =
            Dict.update key (\items -> Just (Maybe.withDefault [] items ++ [ item ]))

        violations =
            List.foldl (\v acc -> List.foldl (\c inner -> add c v inner) acc (markedCells roster v)) Dict.empty roster.checks.violations
    in
    { violations = violations
    , statuses = List.foldl (\s -> add s.registrar s) Dict.empty roster.statuses
    , load = Dict.fromList (List.map (\w -> ( w.registrar, w.load )) roster.checks.workload)
    , maxLoad = List.foldl (.load >> Basics.max) 0 roster.checks.workload
    , selected = Set.empty
    }


statusesOn : Checks -> Int -> Date -> List T.StatusOut
statusesOn checks registrar date =
    Dict.get registrar checks.statuses
        |> Maybe.withDefault []
        |> List.filter (\s -> Date.isBetween s.start s.end date && (List.isEmpty s.weekdays || List.member (Date.weekdayNumber date - 1) s.weekdays))


{-| Whether a status keeps a registrar off a shift type that day, or off all duty when no type is given.
A buddy is still on call, with someone alongside.
-}
rulesOut : Maybe T.ShiftType -> T.StatusOut -> Bool
rulesOut shiftType status =
    status.type_
        /= T.StatusType__BUDDY
        && (case shiftType of
                Nothing ->
                    List.isEmpty status.shift_types

                Just t ->
                    isDuty t && (List.isEmpty status.shift_types || List.member t status.shift_types)
           )


loadOf : Checks -> Int -> Float
loadOf checks registrar =
    Dict.get registrar checks.load |> Maybe.withDefault 0


type Problem
    = Gap Date (List String)
    | Rule T.ViolationOut


problems : Model -> T.RosterOut -> Window -> List Problem
problems model roster window =
    let
        gaps =
            List.concatMap (\date -> List.map (Gap date) (coverGaps model roster window date)) roster.dates
    in
    gaps ++ List.map Rule roster.checks.violations



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
        , div [ class "re-toasts" ] [ viewFailure model.failure, viewToast model.toast ]
        , div [ class "visually-hidden", attribute "aria-live" "polite", attribute "role" "status" ] [ text model.announcement ]
        ]


{-| The page behind a popover or the publish dialog is out of reach until it closes.
-}
behindLayer : Model -> List (Attribute Msg)
behindLayer model =
    inertWhen (model.publish /= Nothing || model.popover /= Nothing)


viewToolbar : Model -> Html Msg
viewToolbar model =
    let
        hiddenCount =
            Set.size model.hiddenShiftTypes + Set.size model.hiddenLeaveTypes
    in
    div ([ class "re-toolbar" ] ++ behindLayer model)
        [ h1 [ class "re-title" ] [ text "Roster" ]
        , case model.roster of
            Just roster ->
                div [ class "re-nav" ]
                    [ div [ class "input-group input-group-sm flex-nowrap w-auto" ]
                        [ button [ type_ "button", class "btn btn-outline-secondary", attribute "aria-label" "Previous week", title "Previous week (Page Up)", onClick (GoToWeek roster.prev) ]
                            [ i [ class "bi bi-chevron-left", attribute "aria-hidden" "true" ] [] ]
                        , input
                            [ type_ "date"
                            , class "form-control re-week-input"
                            , value (Date.toIsoString model.week)
                            , attribute "aria-label" "Go to the week of"
                            , on "change" (Decode.map PickWeek targetValue)
                            ]
                            []
                        , button [ type_ "button", class "btn btn-outline-secondary", attribute "aria-label" "Next week", title "Next week (Page Down)", onClick (GoToWeek roster.next) ]
                            [ i [ class "bi bi-chevron-right", attribute "aria-hidden" "true" ] [] ]
                        ]
                    , button [ type_ "button", class "btn btn-sm btn-outline-secondary", onClick (GoToWeek roster.today) ] [ text "Today" ]
                    , span [ class "re-window" ] [ text (windowLabel roster.dates) ]
                    , viewSelectionNote model roster
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
            , case model.roster of
                Just roster ->
                    viewProblemsButton model roster

                Nothing ->
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
                , title "Key and keyboard (?)"
                , onClick (Open ForKey "key-button")
                ]
                [ i [ class "bi bi-info-circle me-1", attribute "aria-hidden" "true" ] [], text "Key" ]
            , viewPublishedStatus model.roster
            , button [ type_ "button", id "publish-button", class "btn btn-sm btn-primary", onClick OpenPublish ]
                [ i [ class "bi bi-send me-1", attribute "aria-hidden" "true" ] [], text "Publish…" ]
            ]
        ]


viewSelectionNote : Model -> T.RosterOut -> Html Msg
viewSelectionNote model roster =
    let
        count =
            List.length (selectedCells model roster)
    in
    if model.selectFrom /= Nothing && count > 1 then
        span [ class "re-selection" ]
            [ strong [] [ text (plural count "cell" "cells" ++ " selected") ]
            , text ": a shift's key sets them all, Delete clears them, Ctrl+C copies, "
            , kbd [] [ text "Esc" ]
            , text " deselects"
            ]

    else
        text ""


viewProblemsButton : Model -> T.RosterOut -> Html Msg
viewProblemsButton model roster =
    let
        count =
            List.length (problems model roster (windowOf model roster))
    in
    button
        [ type_ "button"
        , id "problems-button"
        , classList [ ( "btn btn-sm re-problems-button", True ), ( "has-problems", count > 0 ) ]
        , attribute "aria-haspopup" "dialog"
        , attribute "aria-expanded" (boolString (isProblems model.popover))
        , onClick (Open ForProblems "problems-button")
        ]
        [ i
            [ class
                (if count > 0 then
                    "bi bi-exclamation-diamond-fill me-1"

                 else
                    "bi bi-check2-circle me-1"
                )
            , attribute "aria-hidden" "true"
            ]
            []
        , text
            (if count == 0 then
                "No problems"

             else
                plural count "problem" "problems"
            )
        , if model.checking then
            span [ class "spinner-border spinner-border-sm ms-1 re-checking", attribute "aria-hidden" "true", title "Checking the rules…" ] []

          else
            text ""
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
            windowOf model roster

        checks =
            if model.selectFrom /= Nothing then
                checksOf roster |> (\c -> { c | selected = Set.fromList (selectedCells model roster) })

            else
                checksOf roster

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
            ++ behindLayer model
        )
        [ if List.isEmpty roster.registrars then
            p [ class "re-empty" ] [ text "No registrars are on the roster in these three weeks." ]

          else
            table
                [ class "re-grid"
                , attribute "role" "grid"
                , attribute "aria-multiselectable" "true"
                , attribute "aria-label" ("Roster, " ++ windowLabel roster.dates)
                , preventDefaultOn "keydown" (gridKeyDecoder model)
                ]
                [ thead []
                    [ tr [ class "re-head" ]
                        (th [ scope "col", class "re-corner" ] [ text "Registrar" ]
                            :: th [ scope "col", class "re-corner re-loadcol", title ("On-call load over the " ++ String.fromInt model.flags.workloadWeeks ++ " weeks to " ++ (List.reverse roster.dates |> List.head |> Maybe.map dayDate |> Maybe.withDefault "")) ]
                                [ span [ class "re-weekday" ] [ text (String.fromInt model.flags.workloadWeeks ++ " wk") ], span [ class "re-daydate" ] [ text "Load" ] ]
                            :: List.indexedMap (viewDateHeader window) roster.dates
                        )
                    , tr [ class "re-cover" ]
                        (th [ scope "row", class "re-corner re-rowlabel" ] [ text "Cover" ]
                            :: td [ class "re-corner re-loadcol" ] []
                            :: List.indexedMap (viewCover model roster window) roster.dates
                        )
                    ]
                , tbody [] (List.map (viewRow model roster window checks cursor) roster.registrars)
                , tfoot []
                    [ tr []
                        (th [ scope "row", class "re-corner re-rowlabel" ] [ text "On leave" ]
                            :: td [ class "re-corner re-loadcol" ] []
                            :: List.indexedMap (viewLeaveCount roster window) roster.dates
                        )
                    ]
                ]
        ]


keyPressDecoder : Decoder KeyPress
keyPressDecoder =
    Decode.map5 KeyPress
        (Decode.field "key" Decode.string)
        (Decode.field "shiftKey" Decode.bool)
        (Decode.map2 (||) (Decode.field "ctrlKey" Decode.bool) (Decode.field "metaKey" Decode.bool))
        (Decode.field "altKey" Decode.bool)
        (Decode.oneOf [ Decode.at [ "target", "id" ] Decode.string, Decode.succeed "" ])


{-| The grid's keys work on its cells; from a cover gap's button, only stepping through problems does.
-}
gridKeyDecoder : Model -> Decoder ( Msg, Bool )
gridKeyDecoder model =
    keyPressDecoder
        |> Decode.andThen
            (\press ->
                let
                    shortcut =
                        List.any (\c -> c.key /= "" && c.key == String.toLower press.key) model.flags.shiftTypes

                    handled =
                        if press.alt || model.popover /= Nothing then
                            False

                        else if String.startsWith "cover-" press.target then
                            not press.command && List.member press.key [ "[", "]" ]

                        else if not (String.startsWith "cell-" press.target) then
                            False

                        else if press.command then
                            List.member (String.toLower press.key) [ "c", "v" ]

                        else
                            shortcut
                                || List.member press.key [ "ArrowUp", "ArrowDown", "ArrowLeft", "ArrowRight", "Home", "End", "PageUp", "PageDown", "Enter", " ", "Delete", "Backspace", "?", "[", "]" ]
                                || (press.key == "Escape" && model.selectFrom /= Nothing)
                in
                if handled then
                    Decode.succeed ( GridKey press, True )

                else
                    Decode.fail "not ours"
            )


columnClasses : Window -> Int -> Date -> List ( String, Bool )
columnClasses window index date =
    [ ( "is-weekend", isWeekend date )
    , ( "is-holiday", Dict.member (day date) window.holidays )
    , ( "is-today", date == window.today )
    , ( "is-unpublished", not (isPublished window date) )
    , ( "is-week-start", index > 0 && Date.weekday date == Time.Mon )
    , ( "is-focus-week", index >= 7 && index < 14 )
    , ( "is-publish-edge", index > 0 && Maybe.map (isPublished window) (previousDate window index) /= Just (isPublished window date) )
    ]


previousDate : Window -> Int -> Maybe Date
previousDate window index =
    List.drop (index - 1) window.dates |> List.head


viewDateHeader : Window -> Int -> Date -> Html Msg
viewDateHeader window index date =
    let
        unpublishedStarts =
            not (isPublished window date) && (index == 0 || Maybe.map (isPublished window) (previousDate window index) == Just True)
    in
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
        , if unpublishedStarts then
            span [ class "re-tag re-tag--unpublished", title "Registrars can't see this day or the ones after it until they're published." ] [ text "Unpublished" ]

          else if not (isPublished window date) then
            span [ class "visually-hidden" ] [ text "Unpublished" ]

          else
            text ""
        ]


{-| Only problems stand out: a covered day is a quiet tick, a gap is a button that opens the day's cover menu.
-}
viewCover : Model -> T.RosterOut -> Window -> Int -> Date -> Html Msg
viewCover model roster window index date =
    let
        rule =
            coverRule model window date

        states =
            List.map (\alternatives -> ( alternatives, coverFor roster date alternatives )) rule

        choice =
            choiceFor model.flags.shiftTypes

        gaps =
            List.filter (\( _, state ) -> state == Missing) states

        posted =
            List.filterMap
                (\( _, state ) ->
                    case state of
                        Posted shiftType ->
                            Just shiftType

                        _ ->
                            Nothing
                )
                states

        coveredNames =
            List.filterMap
                (\( _, state ) ->
                    case state of
                        Covered shiftType ->
                            Just (lowerLabel (choice shiftType).label)

                        _ ->
                            Nothing
                )
                states
    in
    td [ classList (( "re-cover-cell", True ) :: columnClasses window index date) ]
        (List.indexedMap
            (\n ( alternatives, _ ) ->
                button
                    [ type_ "button"
                    , id
                        (if n == 0 then
                            coverId date

                         else
                            coverId date ++ "-" ++ String.fromInt n
                        )
                    , class "re-needs"
                    , attribute "aria-haspopup" "dialog"
                    , attribute "aria-label" (dayDate date ++ " needs " ++ needsLabel model alternatives ++ ": choose who")
                    , title ("Needs " ++ needsLabel model alternatives)
                    , onClick (Open (ForCover date) (coverId date))
                    ]
                    [ i [ class "bi bi-plus-lg", attribute "aria-hidden" "true" ] []
                    , text (String.join "/" (List.map (choice >> .short) alternatives))
                    ]
            )
            gaps
            ++ List.map
                (\shiftType ->
                    span [ class "re-coverchip is-open", title ((choice shiftType).label ++ " posted, not yet given to anyone") ]
                        [ i [ class "bi bi-circle", attribute "aria-hidden" "true" ] []
                        , span [ attribute "aria-hidden" "true" ] [ text (choice shiftType).short ]
                        , span [ class "visually-hidden" ] [ text ((choice shiftType).label ++ " posted, not yet given to anyone") ]
                        ]
                )
                posted
            ++ (if List.isEmpty gaps && List.isEmpty posted && not (List.isEmpty rule) then
                    [ span [ class "re-covered", title ("Covered: " ++ String.join ", " coveredNames) ]
                        [ i [ class "bi bi-check2", attribute "aria-hidden" "true" ] []
                        , span [ class "visually-hidden" ] [ text ("Covered: " ++ String.join ", " coveredNames) ]
                        ]
                    ]

                else
                    []
               )
        )


viewRow : Model -> T.RosterOut -> Window -> Checks -> Maybe Cell -> T.RegistrarOut -> Html Msg
viewRow model roster window checks cursor registrar =
    let
        statuses =
            Dict.get registrar.id checks.statuses |> Maybe.withDefault []

        registrarLoad =
            loadOf checks registrar.id
    in
    tr []
        (th [ scope "row", class "re-name", title (registrar.name ++ " (" ++ registrar.username ++ ")") ]
            [ div [ class "re-nameline" ]
                [ span [ class "re-username" ] [ text registrar.name ]
                , case nullable registrar.year of
                    Just year ->
                        span [ class "re-year" ]
                            [ text ("Y" ++ String.fromInt year)
                            , span [ class "visually-hidden" ] [ text (", year " ++ String.fromInt year) ]
                            ]

                    Nothing ->
                        text ""
                ]
            , if List.isEmpty statuses then
                text ""

              else
                div [ class "re-statuses" ] (List.map (viewStatusBadge model) statuses)
            ]
            :: td [ class "re-load", title ("On-call load " ++ formatLoad registrarLoad ++ " over " ++ String.fromInt model.flags.workloadWeeks ++ " weeks") ]
                [ span [ class "re-loadvalue" ] [ text (formatLoad registrarLoad) ]
                , span [ class "re-loadbar", attribute "aria-hidden" "true" ]
                    [ span [ style "width" (String.fromFloat (100 * registrarLoad / Basics.max 0.1 checks.maxLoad) ++ "%") ] [] ]
                ]
            :: List.indexedMap (\index date -> viewCell model roster window checks cursor registrar index date) roster.dates
        )


viewStatusBadge : Model -> T.StatusOut -> Html Msg
viewStatusBadge model status =
    let
        choice =
            statusChoice model status.type_
    in
    span [ class ("re-status-badge is-" ++ String.toLower (T.statusTypeToString status.type_)), title (statusSentence model status) ]
        [ text choice.short
        , span [ class "visually-hidden" ] [ text (": " ++ statusSentence model status) ]
        ]


{-| "Pre-exam 20 Oct – 3 Nov: no nights. Sitting the part 1."
-}
statusSentence : Model -> T.StatusOut -> String
statusSentence model status =
    let
        choice =
            statusChoice model status.type_

        weekdays =
            if List.isEmpty status.weekdays then
                ""

            else
                " on " ++ String.join ", " (List.map weekdayName status.weekdays)

        types =
            if List.isEmpty status.shift_types then
                ""

            else
                ": no " ++ String.join " or " (List.map (shiftLabel model) status.shift_types)
    in
    choice.label
        ++ weekdays
        ++ ", "
        ++ dayMonth status.start
        ++ " – "
        ++ dayMonth status.end
        ++ types
        ++ (if String.isEmpty status.comment then
                ""

            else
                ". " ++ status.comment
           )


weekdayName : Int -> String
weekdayName n =
    Date.format "EEE" (Date.fromWeekDate 2026 1 (Date.numberToWeekday (n + 1)))


viewCell : Model -> T.RosterOut -> Window -> Checks -> Maybe Cell -> T.RegistrarOut -> Int -> Date -> Html Msg
viewCell model roster window checks cursor registrar index date =
    let
        cell =
            ( registrar.id, day date )

        shifts =
            cellShifts roster cell

        leaves =
            cellLeaves roster cell

        violations =
            Dict.get cell checks.violations |> Maybe.withDefault []

        offDuty =
            statusesOn checks registrar.id date |> List.filter (rulesOut Nothing)

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
             , ( "has-problem", not (List.isEmpty violations) )
             , ( "is-off", not (List.isEmpty offDuty) )
             , ( "is-open", isCellOpen cell model.popover )
             , ( "is-selected", Set.member cell checks.selected )
             ]
                ++ columnClasses window index date
            )
        , attribute "aria-label" (cellLabel model registrar date shifts leaves violations offDuty)
        , attribute "aria-busy" (boolString saving)
        , attribute "aria-haspopup" "dialog"
        , onFocus (Focused cell)
        , attribute "aria-selected" (boolString (Set.member cell checks.selected))
        , on "click" (Decode.map (CellClick cell) (Decode.field "shiftKey" Decode.bool))
        ]
        [ div [ class "re-cellbox" ]
            (let
                compact =
                    List.length visibleShifts + List.length visibleLeaves > 1
             in
             List.map (viewShiftChip model compact) visibleShifts
                ++ List.map (viewLeaveChip model compact) visibleLeaves
            )
        , if List.isEmpty violations then
            text ""

          else
            span [ class "re-flag", title (String.join "\n" (List.map .message violations)) ]
                [ i [ class "bi bi-exclamation-diamond-fill", attribute "aria-hidden" "true" ] [] ]
        , if List.isEmpty visibleShifts && List.isEmpty visibleLeaves then
            span [ class "re-add", attribute "aria-hidden" "true" ] [ text "+" ]

          else
            text ""
        ]


{-| What a screen reader says for a cell: who, when, what's there and what's wrong.
-}
cellLabel : Model -> T.RegistrarOut -> Date -> List T.ShiftOut -> List T.LeaveOut -> List T.ViolationOut -> List T.StatusOut -> String
cellLabel model registrar date shifts leaves violations offDuty =
    let
        contents =
            List.map (\s -> (shiftChoice model s.type_).label ++ extraLabel s) shifts
                ++ List.map (\l -> (leaveChoice model l.type_).label ++ " leave" ++ portionLabel l ++ ", " ++ leaveStateName (leaveState l)) leaves

        extraLabel s =
            if s.extra_duty then
                " (extra duty)"

            else
                ""
    in
    registrar.name
        ++ ", "
        ++ dayDate date
        ++ ": "
        ++ (if List.isEmpty contents then
                "empty"

            else
                String.join "; " contents
           )
        ++ (if List.isEmpty offDuty then
                ""

            else
                ". Not on call: " ++ String.join ", " (List.map (.type_ >> statusChoice model >> .label >> String.toLower) offDuty)
           )
        ++ (case List.length violations of
                0 ->
                    ""

                n ->
                    ". Breaks " ++ plural n "rule" "rules"
           )


{-| In a cell holding more than one thing, a shift shows as its key letter and leave as its state icon,
so both fit; the title and the cell's label still name them in full.
-}
viewShiftChip : Model -> Bool -> T.ShiftOut -> Html Msg
viewShiftChip model compact shift =
    let
        choice =
            shiftChoice model shift.type_
    in
    span [ classList [ ( "re-chip re-shift " ++ shiftClass shift.type_, True ), ( "is-compact", compact ) ], title choice.label, attribute "aria-hidden" "true" ]
        [ text
            (if compact && choice.key /= "" then
                String.toUpper choice.key

             else
                choice.short
            )
        , if shift.extra_duty then
            span [ class "re-extra" ] [ i [ class "bi bi-coin" ] [] ]

          else
            text ""
        ]


viewLeaveChip : Model -> Bool -> T.LeaveOut -> Html Msg
viewLeaveChip model compact leave =
    let
        choice =
            leaveChoice model leave.type_

        state =
            leaveState leave
    in
    span [ classList [ ( "re-chip re-leave is-" ++ leaveStateClass state, True ), ( "is-compact", compact ) ], title (choice.label ++ " leave" ++ portionLabel leave ++ ", " ++ leaveStateName state), attribute "aria-hidden" "true" ]
        [ i [ class ("bi " ++ leaveIcon state) ] []
        , if compact then
            text (String.trim (portionPrefix leave))

          else
            text (portionPrefix leave ++ choice.short)
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

        count n icon cls =
            if n > 0 then
                span [ class cls, attribute "aria-hidden" "true" ] [ i [ class ("bi " ++ icon) ] [], text (String.fromInt n) ]

            else
                text ""
    in
    td [ classList (( "re-count", True ) :: columnClasses window index date) ]
        (if List.isEmpty onDay then
            [ span [ class "visually-hidden" ] [ text "No one on leave" ] ]

         else
            [ count approved "bi-check-lg" "re-count-approved"
            , count waiting "bi-hourglass-split" "re-count-pending"
            , span [ class "visually-hidden" ] [ text (String.fromInt approved ++ " approved, " ++ String.fromInt waiting ++ " waiting") ]
            ]
        )



-- POPOVERS


viewPopover : Model -> Html Msg
viewPopover model =
    case ( model.popover, model.roster ) of
        ( Just (CellMenu cell anchor confirm), Just roster ) ->
            popoverShell anchor 360 (describeCellLong model roster cell) [ preventDefaultOn "keydown" (cellMenuKeys model confirm) ] (viewCellMenu model roster cell confirm)

        ( Just (CoverMenu date anchor), Just roster ) ->
            popoverShell anchor 380 ("Cover for " ++ dayDate date ++ holidaySuffix roster date) [] (viewCoverMenu model roster date)

        ( Just (ManyMenu anchor question changes), _ ) ->
            popoverShell anchor
                320
                "Delete shifts"
                []
                [ p [ class "mt-2 mb-2" ] [ text question ]
                , div [ class "d-flex gap-2 mb-2" ]
                    [ button [ type_ "button", id "confirm-action", class "btn btn-sm btn-danger", onClick (SaveMany ("Deleted " ++ plural (List.length changes) "shift" "shifts") changes) ]
                        [ text ("Delete " ++ plural (List.length changes) "shift" "shifts") ]
                    , button [ type_ "button", class "btn btn-sm btn-outline-secondary", onClick ClosePopover ] [ text "Keep them" ]
                    ]
                ]

        ( Just (ProblemsMenu anchor), Just roster ) ->
            popoverShell anchor 420 "Problems in these three weeks" [] (viewProblems model roster)

        ( Just (FiltersMenu anchor), _ ) ->
            popoverShell anchor 300 "Show in the grid" [] (viewFilters model)

        ( Just (KeyMenu anchor), _ ) ->
            popoverShell anchor 380 "Key" [] (viewKey model)

        _ ->
            text ""


{-| A shift's key works in the cell's menu just as in the grid.
-}
cellMenuKeys : Model -> Confirm -> Decoder ( Msg, Bool )
cellMenuKeys model confirm =
    Decode.map2 Tuple.pair (Decode.field "key" Decode.string) inTextField
        |> Decode.andThen
            (\( key, typing ) ->
                if not typing && (confirm == NoConfirm || confirm == AddingAnother) && List.any (\c -> c.key /= "" && c.key == String.toLower key) model.flags.shiftTypes then
                    Decode.succeed ( GridKey { key = key, shift = False, command = False, alt = False, target = "popover" }, True )

                else
                    Decode.fail "not ours"
            )


{-| A popover in a fixed layer, opening below its anchor, or above it when the anchor is low on screen.
Its body scrolls between a fixed heading and footer. Focus starts on the heading and stays inside: the
sentinels at either end send it back round.
-}
popoverShell : Anchor -> Float -> String -> List (Attribute Msg) -> List (Html Msg) -> Html Msg
popoverShell anchor width heading extra content =
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
             , style "width" (px (Basics.min width (anchor.viewportWidth - 16)))
             ]
                ++ vertical
                ++ extra
            )
            [ span [ tabindex 0, onFocus (FocusId "popover-last") ] []
            , div [ class "re-popover-head" ]
                [ h2 [ id "popover-title", class "re-popover-title", tabindex -1 ] [ text heading ] ]
            , div [ class "re-popover-body" ] content
            , div [ class "re-popover-foot" ]
                [ span [ class "re-meta m-0" ] [ kbd [] [ text "Esc" ], text " closes" ]
                , button [ type_ "button", id "popover-last", class "btn btn-sm btn-outline-secondary", onClick ClosePopover ] [ text "Close" ]
                ]
            , span [ tabindex 0, onFocus (FocusId "popover-title") ] []
            ]
        ]


describeCellLong : Model -> T.RosterOut -> Cell -> String
describeCellLong model roster ( registrar, d ) =
    registrarName model registrar ++ " · " ++ dayDate (Date.fromRataDie d) ++ holidaySuffix roster (Date.fromRataDie d)


holidaySuffix : T.RosterOut -> Date -> String
holidaySuffix roster date =
    roster.holidays |> List.filter (\h -> h.date == date) |> List.head |> Maybe.map (\h -> " · " ++ h.name) |> Maybe.withDefault ""


viewCellMenu : Model -> T.RosterOut -> Cell -> Confirm -> List (Html Msg)
viewCellMenu model roster (( registrar, d ) as cell) confirm =
    let
        date =
            Date.fromRataDie d

        shifts =
            cellShifts roster cell

        leaves =
            cellLeaves roster cell

        window =
            windowOf model roster

        checks =
            checksOf roster

        violations =
            Dict.get cell checks.violations |> Maybe.withDefault []

        statuses =
            statusesOn checks registrar date
    in
    (case confirm of
        ConfirmOnLeave change ->
            [ viewConfirmOnLeave model roster cell change ]

        _ ->
            []
    )
        ++ (if List.isEmpty violations then
                []

            else
                [ section [ class "re-section" ]
                    [ h3 [ class "re-section-title" ] [ text (plural (List.length violations) "rule break" "rule breaks") ]
                    , ul [ class "re-rulelist" ] (List.map viewViolation violations)
                    ]
                ]
           )
        ++ List.map (\s -> p [ class "re-note" ] [ i [ class "bi bi-person-badge me-1", attribute "aria-hidden" "true" ] [], text (statusSentence model s) ]) statuses
        ++ (if not (isPublished window date) then
                [ p [ class "re-note" ] [ i [ class "bi bi-eye-slash me-1", attribute "aria-hidden" "true" ] [], text "Not published yet: registrars can't see this day." ] ]

            else
                []
           )
        ++ List.map (viewLeaveSection model roster cell) leaves
        ++ List.map (viewShiftSection model cell statuses confirm) shifts
        ++ [ viewAddSection model cell statuses shifts (List.any isActiveLeave leaves) confirm ]


viewViolation : T.ViolationOut -> Html Msg
viewViolation violation =
    li []
        [ span [ class "re-clause" ] [ text (nullable violation.clause |> Maybe.withDefault "Department rule") ]
        , text violation.message
        ]


viewConfirmOnLeave : Model -> T.RosterOut -> Cell -> Change -> Html Msg
viewConfirmOnLeave model roster cell change =
    let
        leave =
            cellLeaves roster cell |> List.filter isActiveLeave |> List.head

        onLeave =
            case leave of
                Just l ->
                    registrarName model (Tuple.first cell) ++ " is on " ++ String.toLower (leaveChoice model l.type_).label ++ " leave" ++ portionLabel l ++ ", " ++ leaveStateName (leaveState l) ++ "."

                Nothing ->
                    ""

        ( question, action ) =
            case change of
                AddShift _ shiftType _ _ ->
                    ( "Add " ++ withArticle (shiftLabel model shiftType) ++ " anyway?", "Add " ++ shiftLabel model shiftType ++ " anyway" )

                ChangeShift _ before patch ->
                    let
                        to =
                            Maybe.map (shiftLabel model) patch.type_ |> Maybe.withDefault ""
                    in
                    ( "Change the " ++ shiftLabel model before.type_ ++ " to " ++ withArticle to ++ " anyway?", "Change to " ++ to ++ " anyway" )

                _ ->
                    ( "", "Save anyway" )
    in
    section [ class "re-section re-confirm" ]
        [ p [ class "mb-2" ] [ strong [] [ text onLeave ], text (" " ++ question) ]
        , div [ class "d-flex gap-2" ]
            [ button [ type_ "button", id "confirm-action", class "btn btn-sm btn-primary", onClick (Save Fresh change) ] [ text action ]
            , button [ type_ "button", class "btn btn-sm btn-outline-secondary", onClick (Open (ForCell cell NoConfirm) (cellId cell)) ] [ text "Cancel" ]
            ]
        ]


viewShiftSection : Model -> Cell -> List T.StatusOut -> Confirm -> T.ShiftOut -> Html Msg
viewShiftSection model cell statuses confirm shift =
    section [ class "re-section" ]
        (h3 [ class "re-section-title" ]
            [ span [ class ("re-chip re-shift " ++ shiftClass shift.type_), attribute "aria-hidden" "true" ] [ text (shiftChoice model shift.type_).short ]
            , text
                ((shiftChoice model shift.type_).label
                    ++ (if shift.extra_duty then
                            " (extra duty)"

                        else
                            ""
                       )
                )
            ]
            :: (if confirm == ConfirmDelete shift.id then
                    [ p [ class "mb-2" ]
                        [ text ("Delete " ++ possessive (registrarName model (Tuple.first cell)) ++ " " ++ shiftLabel model shift.type_ ++ " on " ++ dayDate shift.date ++ "? You can undo it.") ]
                    , div [ class "d-flex gap-2" ]
                        [ button [ type_ "button", id "confirm-action", class "btn btn-sm btn-danger", onClick (Save Fresh (DeleteShift cell shift)) ] [ text "Delete shift" ]
                        , button [ type_ "button", class "btn btn-sm btn-outline-secondary", onClick (Open (ForCell cell NoConfirm) (cellId cell)) ] [ text "Keep it" ]
                        ]
                    ]

                else
                    [ div [ class "re-label", id ("change-" ++ String.fromInt shift.id) ] [ text "Change to" ]
                    , div [ class "re-typegrid", attribute "role" "group", attribute "aria-labelledby" ("change-" ++ String.fromInt shift.id) ]
                        (shiftChoices model
                            |> List.filter (\( shiftType, _ ) -> shiftType /= shift.type_)
                            |> List.map
                                (\( shiftType, choice ) ->
                                    typeButton statuses
                                        shiftType
                                        choice
                                        [ attribute "aria-label" ("Change to " ++ choice.label)
                                        , onClick (Request (ChangeShift cell shift { type_ = Just shiftType, extra_duty = Nothing }))
                                        ]
                                )
                        )
                    , div [ class "d-flex gap-2 mt-2" ]
                        [ button
                            [ type_ "button"
                            , class "btn btn-sm btn-outline-secondary"
                            , attribute "aria-pressed" (boolString shift.extra_duty)
                            , onClick (Save Fresh (ChangeShift cell shift { type_ = Nothing, extra_duty = Just (not shift.extra_duty) }))
                            ]
                            [ i [ class "bi bi-coin me-1", attribute "aria-hidden" "true" ] []
                            , text "Extra duty"
                            ]
                        , button [ type_ "button", class "btn btn-sm btn-outline-danger ms-auto", onClick (AskDelete cell shift.id) ]
                            [ i [ class "bi bi-trash3 me-1", attribute "aria-hidden" "true" ] [], text "Delete…" ]
                        ]
                    ]
               )
        )


{-| A shift type to pick, marked when one of the registrar's statuses rules it out that day.
-}
typeButton : List T.StatusOut -> T.ShiftType -> Choice -> List (Attribute Msg) -> Html Msg
typeButton statuses shiftType choice attributes =
    let
        ruledOut =
            List.any (rulesOut (Just shiftType)) statuses
    in
    button ([ type_ "button", classList [ ( "btn btn-sm re-typebtn", True ), ( "is-ruled-out", ruledOut ) ] ] ++ attributes)
        [ span [ class ("re-swatch " ++ shiftClass shiftType), attribute "aria-hidden" "true" ] []
        , text choice.label
        , if ruledOut then
            span [ class "re-ruledout", title "Their status rules this out" ]
                [ i [ class "bi bi-slash-circle", attribute "aria-hidden" "true" ] []
                , span [ class "visually-hidden" ] [ text " (their status rules this out)" ]
                ]

          else
            text ""
        , kbd [ attribute "aria-hidden" "true" ] [ text (String.toUpper choice.key) ]
        ]


viewAddSection : Model -> Cell -> List T.StatusOut -> List T.ShiftOut -> Bool -> Confirm -> Html Msg
viewAddSection model cell statuses shifts onLeave confirm =
    let
        grid =
            div [ class "re-typegrid" ]
                (List.indexedMap
                    (\index ( shiftType, choice ) ->
                        typeButton statuses
                            shiftType
                            choice
                            ([ attribute "aria-label" ("Add " ++ choice.label), onClick (Request (AddShift cell shiftType False Nothing)) ]
                                ++ (if index == 0 then
                                        [ id "add-first" ]

                                    else
                                        []
                                   )
                            )
                    )
                    (shiftChoices model)
                )
    in
    if List.isEmpty shifts && (not onLeave || confirm == AddingAnother) then
        section [ class "re-section" ] [ h3 [ class "re-section-title" ] [ text "Add a shift" ], grid ]

    else if List.isEmpty shifts then
        section [ class "re-section" ]
            [ button [ type_ "button", class "btn btn-sm btn-link px-0", onClick (AddAnother cell) ] [ text "Add a shift on this day of leave…" ] ]

    else if confirm == AddingAnother then
        section [ class "re-section" ]
            [ h3 [ class "re-section-title" ] [ text "Add another shift" ]
            , p [ class "re-meta mt-0 mb-2" ] [ text "Two periods of duty on one day break the contract; an RDO or sleep day alongside is fine." ]
            , grid
            ]

    else
        section [ class "re-section" ]
            [ button [ type_ "button", class "btn btn-sm btn-link px-0", onClick (AddAnother cell) ] [ text "Add another shift…" ] ]


viewLeaveSection : Model -> T.RosterOut -> Cell -> T.LeaveOut -> Html Msg
viewLeaveSection model roster cell leave =
    let
        choice =
            leaveChoice model leave.type_

        state =
            leaveState leave

        request =
            leaveRequest roster leave

        days =
            List.length request

        targets =
            if days > 1 && model.wholeRequest then
                request

            else
                [ leave ]

        change leaveChange =
            Save Fresh (ChangeLeaves cell targets leaveChange)
    in
    section [ class "re-section" ]
        [ h3 [ class "re-section-title" ]
            [ span [ class ("re-chip re-leave is-" ++ leaveStateClass state), attribute "aria-hidden" "true" ]
                [ i [ class ("bi " ++ leaveIcon state) ] [], text (portionPrefix leave ++ choice.short) ]
            , text (choice.label ++ " leave" ++ portionLabel leave)
            ]
        , p [ class "re-status" ] [ text (leaveStateSentence leave) ]
        , if String.isEmpty leave.comment then
            text ""

          else
            p [ class "re-comment" ] [ text ("“" ++ leave.comment ++ "”") ]
        , if days > 1 then
            div [ class "form-check re-request" ]
                [ input
                    [ type_ "checkbox"
                    , class "form-check-input"
                    , id ("whole-" ++ String.fromInt leave.id)
                    , checked model.wholeRequest
                    , onCheck SetWholeRequest
                    ]
                    []
                , label [ class "form-check-label", for ("whole-" ++ String.fromInt leave.id) ]
                    [ text ("Apply to the whole request: " ++ plural days "day" "days" ++ ", " ++ requestSpan request) ]
                ]

          else
            text ""
        , approvalGroup model leave "reg" "Chief registrar" (nullable leave.reg_approved) (decidedBy model leave.reg_decided_by leave.reg_decided_at) (\v -> change { noLeaveChange | reg = Just v })
        , approvalGroup model leave "dot" "Director of Training" (nullable leave.dot_approved) (decidedBy model leave.dot_decided_by leave.dot_decided_at) (\v -> change { noLeaveChange | dot = Just v })
        , div [ class "re-steps" ]
            [ span [ classList [ ( "re-step", True ), ( "is-done", leave.printed ) ] ]
                [ i
                    [ class
                        (if leave.printed then
                            "bi bi-printer-fill me-1"

                         else
                            "bi bi-printer me-1"
                        )
                    , attribute "aria-hidden" "true"
                    ]
                    []
                , text
                    (if leave.printed then
                        "Form printed"

                     else
                        "Form not printed"
                    )
                ]
            , div [ class "form-check form-switch m-0" ]
                [ input
                    [ type_ "checkbox"
                    , class "form-check-input"
                    , attribute "role" "switch"
                    , id ("microster-" ++ String.fromInt leave.id)
                    , checked leave.microster
                    , onCheck (\v -> change { noLeaveChange | microster = Just v })
                    ]
                    []
                , label [ class "form-check-label", for ("microster-" ++ String.fromInt leave.id) ] [ text "In Microster" ]
                ]
            ]
        , div [ class "mt-2" ]
            [ button
                [ type_ "button"
                , class "btn btn-sm btn-outline-secondary"
                , onClick (change { noLeaveChange | cancelled = Just (not leave.cancelled) })
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


{-| "Mon 19 – Wed 21 Oct"
-}
requestSpan : List T.LeaveOut -> String
requestSpan request =
    case ( List.head request, List.head (List.reverse request) ) of
        ( Just first, Just last ) ->
            Date.format "EEE d" first.date
                ++ (if Date.month first.date /= Date.month last.date then
                        " " ++ Date.format "MMM" first.date

                    else
                        ""
                   )
                ++ " – "
                ++ dayDate last.date

        _ ->
            ""


decidedBy : Model -> Nullable String -> Nullable Time.Posix -> Maybe String
decidedBy model by at =
    case ( nullable by, nullable at ) of
        ( Just name, Just time ) ->
            Just ("by " ++ name ++ ", " ++ dateTime model.zone time)

        ( Nothing, Just time ) ->
            Just (dateTime model.zone time)

        ( Just name, Nothing ) ->
            Just ("by " ++ name)

        ( Nothing, Nothing ) ->
            Nothing


{-| One approver's decision as a group of radio buttons, and who made it.
-}
approvalGroup : Model -> T.LeaveOut -> String -> String -> Maybe Bool -> Maybe String -> (Maybe Bool -> Msg) -> Html Msg
approvalGroup _ leave approver who current decided toMsg =
    let
        groupName =
            approver ++ "-" ++ String.fromInt leave.id

        option value optionLabel variant =
            let
                optionId =
                    groupName ++ "-" ++ String.toLower optionLabel
            in
            [ input
                [ type_ "radio"
                , class "btn-check"
                , name groupName
                , id optionId
                , checked (current == value)
                , disabled leave.cancelled
                , onCheck (\_ -> toMsg value)
                ]
                []
            , label [ class ("btn btn-sm btn-outline-" ++ variant), for optionId ] [ text optionLabel ]
            ]
    in
    fieldset [ class "re-approval" ]
        [ legend [ class "re-label" ] [ text who ]
        , div [ class "btn-group btn-group-sm" ]
            (option (Just True) "Approve" "success" ++ option Nothing "Waiting" "secondary" ++ option (Just False) "Decline" "danger")
        , case ( current, decided ) of
            ( Just _, Just line ) ->
                span [ class "re-decided" ] [ text line ]

            ( Just _, Nothing ) ->
                span [ class "re-decided" ] [ text "decided before decisions were recorded" ]

            ( Nothing, _ ) ->
                text ""
        ]


{-| A cover gap's menu: who could fill it, least loaded first, and who can't and why.
-}
viewCoverMenu : Model -> T.RosterOut -> Date -> List (Html Msg)
viewCoverMenu model roster date =
    let
        window =
            windowOf model roster

        checks =
            checksOf roster

        gaps =
            coverGaps model roster window date

        candidate registrar =
            let
                cell =
                    ( registrar.id, day date )

                leave =
                    cellLeaves roster cell |> List.filter isActiveLeave

                rostered =
                    cellShifts roster cell

                statuses =
                    statusesOn checks registrar.id date
            in
            if List.any (\l -> l.portion == "ALL") leave then
                Err "on leave"

            else if not (List.isEmpty rostered) then
                Err "already rostered"

            else if List.any (rulesOut Nothing) statuses then
                Err "not on call (status)"

            else
                Ok ( registrar, statuses, leave )

        ( available, unavailable ) =
            List.foldr
                (\r ( ok, no ) ->
                    case candidate r of
                        Ok c ->
                            ( c :: ok, no )

                        Err reason ->
                            ( ok, reason :: no )
                )
                ( [], [] )
                roster.registrars

        ranked =
            List.sortBy (\( r, _, _ ) -> loadOf checks r.id) available

        reasons =
            unavailable
                |> groupBy identity
                |> List.map (\group -> String.fromInt (List.length group) ++ " " ++ (List.head group |> Maybe.withDefault ""))
    in
    if List.isEmpty gaps then
        [ p [ class "re-note is-ok mt-2" ] [ i [ class "bi bi-check2 me-1", attribute "aria-hidden" "true" ] [], text "This day is covered." ] ]

    else
        List.map
            (\alternatives ->
                section [ class "re-section" ]
                    [ h3 [ class "re-section-title" ] [ text ("Needs " ++ needsLabel model alternatives) ]
                    , p [ class "re-meta mt-0 mb-2" ] [ text "Least on-call load first. Rule breaks show once it's saved, and you can undo." ]
                    , ul [ class "re-candidates" ]
                        (List.map
                            (\( registrar, statuses, halfDay ) ->
                                li []
                                    [ span [ class "re-candidate" ]
                                        [ span [ class "re-candidate-name" ] [ text registrar.name ]
                                        , span [ class "re-meta m-0" ]
                                            [ text
                                                ("load "
                                                    ++ formatLoad (loadOf checks registrar.id)
                                                    ++ (List.map (\s -> " · " ++ (statusChoice model s.type_).short) statuses |> String.concat)
                                                    ++ (List.map (\l -> " · " ++ l.portion ++ " leave") halfDay |> String.concat)
                                                )
                                            ]
                                        ]
                                    , span [ class "re-candidate-actions" ]
                                        (List.filterMap
                                            (\value ->
                                                T.shiftTypeFromString value
                                                    |> Maybe.map
                                                        (\shiftType ->
                                                            let
                                                                choice =
                                                                    shiftChoice model shiftType
                                                            in
                                                            button
                                                                [ type_ "button"
                                                                , classList [ ( "btn btn-sm re-typebtn", True ), ( "is-ruled-out", List.any (rulesOut (Just shiftType)) statuses ) ]
                                                                , attribute "aria-label" ("Give " ++ registrar.name ++ " the " ++ shiftLabel model shiftType)
                                                                , onClick (AssignCover (AddShift ( registrar.id, day date ) shiftType False Nothing))
                                                                ]
                                                                [ span [ class ("re-swatch " ++ shiftClass shiftType), attribute "aria-hidden" "true" ] [], text choice.short ]
                                                        )
                                            )
                                            alternatives
                                        )
                                    ]
                            )
                            ranked
                        )
                    , if List.isEmpty ranked then
                        p [ class "re-note is-warning" ] [ text "Nobody is free this day." ]

                      else
                        text ""
                    ]
            )
            gaps
            ++ (if List.isEmpty reasons then
                    []

                else
                    [ p [ class "re-meta mb-2" ] [ text ("Not listed: " ++ String.join ", " reasons ++ ".") ] ]
               )


viewProblems : Model -> T.RosterOut -> List (Html Msg)
viewProblems model roster =
    let
        window =
            windowOf model roster

        all =
            problems model roster window

        gaps =
            List.filterMap
                (\p ->
                    case p of
                        Gap date alternatives ->
                            Just ( date, alternatives )

                        _ ->
                            Nothing
                )
                all

        rules =
            List.filterMap
                (\p ->
                    case p of
                        Rule v ->
                            Just v

                        _ ->
                            Nothing
                )
                all

        shown =
            Set.fromList (List.map day roster.dates)

        firstShown violation =
            violation.dates |> List.filter (\d -> Set.member (day d) shown) |> List.head
    in
    if List.isEmpty all then
        [ p [ class "re-note is-ok mt-2" ] [ i [ class "bi bi-check2-circle me-1", attribute "aria-hidden" "true" ] [], text "No cover gaps or rule breaks in these three weeks." ] ]

    else
        (if List.isEmpty gaps then
            []

         else
            [ section [ class "re-section" ]
                [ h3 [ class "re-section-title" ] [ text ("Cover gaps (" ++ String.fromInt (List.length gaps) ++ ")") ]
                , ul [ class "re-problemlist" ]
                    (List.map
                        (\( date, alternatives ) ->
                            li []
                                [ button [ type_ "button", class "re-problem", onClick (GoToCover date) ]
                                    [ span [ class "re-problem-when" ] [ text (dayDate date) ]
                                    , text ("Needs " ++ needsLabel model alternatives)
                                    ]
                                ]
                        )
                        gaps
                    )
                ]
            ]
        )
            ++ (if List.isEmpty rules then
                    []

                else
                    [ section [ class "re-section" ]
                        [ h3 [ class "re-section-title" ] [ text ("Rule breaks (" ++ String.fromInt (List.length rules) ++ ")") ]
                        , ul [ class "re-problemlist" ]
                            (List.map
                                (\v ->
                                    li []
                                        [ button
                                            [ type_ "button"
                                            , class "re-problem"
                                            , onClick
                                                (case firstShown v of
                                                    Just d ->
                                                        GoToCell ( v.registrar, day d )

                                                    Nothing ->
                                                        NoOp
                                                )
                                            ]
                                            [ span [ class "re-problem-when" ] [ text (registrarName model v.registrar) ]
                                            , span [ class "re-clause" ] [ text (nullable v.clause |> Maybe.withDefault "Department rule") ]
                                            , text v.message
                                            ]
                                        ]
                                )
                                rules
                            )
                        ]
                    ]
               )


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
        , p [ class "re-meta" ] [ i [ class "bi bi-coin me-1", attribute "aria-hidden" "true" ] [], text "marks an extra duty, which doesn't count towards load." ]
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
        [ h3 [ class "re-section-title" ] [ text "Checks" ]
        , ul [ class "re-keylist" ]
            [ li [] [ span [ class "re-keycell" ] [ i [ class "bi bi-exclamation-diamond-fill re-flag-key", attribute "aria-hidden" "true" ] [] ], text "Breaks a contract or department rule: open the day for the clause" ]
            , li [] [ span [ class "re-keycell is-off" ] [], text "Not on call: their status (e.g. pre-exam) rules out duty" ]
            , li [] [ span [ class "re-status-badge" ] [ text "Exam" ], text "Status in these weeks" ]
            , li [] [ span [ class "re-loadvalue" ] [ text "2.4" ], text ("Load: weighted on-call over " ++ String.fromInt model.flags.workloadWeeks ++ " weeks") ]
            , li [] [ span [ class "re-needs" ] [ i [ class "bi bi-plus-lg", attribute "aria-hidden" "true" ] [], text "Swing" ], text "Cover gap: choose who" ]
            , li [] [ span [ class "re-coverchip is-open" ] [ i [ class "bi bi-circle", attribute "aria-hidden" "true" ] [], text "Night" ], text "Posted as an extra duty, not given out" ]
            , li [] [ span [ class "re-covered" ] [ i [ class "bi bi-check2", attribute "aria-hidden" "true" ] [] ], text "Day covered" ]
            ]
        ]
    , section [ class "re-section" ]
        [ h3 [ class "re-section-title" ] [ text "Days" ]
        , ul [ class "re-keylist" ]
            [ li [] [ span [ class "re-keycell is-weekend" ] [ text "Sat" ], text "Weekend" ]
            , li [] [ span [ class "re-keycell is-holiday" ] [ text "Hol" ], text "Public holiday (stat day)" ]
            , li [] [ span [ class "re-keycell is-unpublished" ] [], text "Not published: registrars can't see it" ]
            , li [] [ span [ class "re-keycell is-publish-edge" ] [], text "Where the published range ends" ]
            ]
        ]
    , section [ class "re-section" ]
        [ h3 [ class "re-section-title" ] [ text "Keyboard" ]
        , ul [ class "re-keylist is-keys" ]
            [ li [] [ kbd [] [ text "← ↑ → ↓" ], text "Move between days and registrars" ]
            , li [] [ kbd [] [ text "Home End" ], text "First or last day of the row" ]
            , li [] [ kbd [] [ text "PgUp PgDn" ], text "A week back or on" ]
            , li [] [ kbd [] [ text "Enter Space" ], text "Open the day" ]
            , li [] [ kbd [] [ text (String.join " " (List.map (\( _, c ) -> String.toUpper c.key) (shiftChoices model))) ], text "Add that shift, or change the one there (also in the day's menu)" ]
            , li [] [ kbd [] [ text "Delete" ], text "Delete the day's shift (asks first)" ]
            , li [] [ kbd [] [ text "Shift ←↑→↓" ], text "Select a block of cells (or Shift-click)" ]
            , li [] [ kbd [] [ text "Ctrl C, V" ], text "Copy the selected shifts, paste them at the cursor" ]
            , li [] [ kbd [] [ text "] [" ], text "Next or previous problem" ]
            , li [] [ kbd [] [ text "Ctrl Z" ], text "Undo the last change" ]
            , li [] [ kbd [] [ text "?" ], text "This key" ]
            , li [] [ kbd [] [ text "Esc" ], text "Close and go back" ]
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

                changes =
                    publishChanges model draft

                hiding =
                    draft.preview |> Maybe.map (\p -> p.shifts_hidden + p.leave_hidden > 0) |> Maybe.withDefault False

                field fieldId labelText current toMsg =
                    div [ class "col" ]
                        [ label [ class "form-label", for fieldId ] [ text labelText ]
                        , input [ type_ "date", class "form-control", id fieldId, value current, onInput toMsg ] []
                        ]
            in
            div []
                [ div [ class "modal d-block re-publish", attribute "role" "dialog", attribute "aria-modal" "true", attribute "aria-labelledby" "publish-title" ]
                    [ div [ class "modal-dialog modal-dialog-scrollable" ]
                        [ Html.form [ class "modal-content", onSubmit SavePublish ]
                            [ span [ tabindex 0, onFocus (FocusId "publish-submit") ] []
                            , div [ class "modal-header" ]
                                [ h2 [ class "modal-title fs-5", id "publish-title" ] [ text "Publish the roster" ] ]
                            , div [ class "modal-body" ]
                                [ p [ class "text-body-secondary" ] [ text "Registrars see shifts and leave between these dates in the calendar and their phone calendar feeds. The dashed line on the roster shows where this range ends." ]
                                , div [ class "row g-3" ]
                                    [ field "publish-start" "From" draft.start SetPublishStart
                                    , field "publish-end" "To" draft.end SetPublishEnd
                                    ]
                                , if not valid then
                                    p [ class "re-note is-error mt-3 mb-0", attribute "role" "alert" ] [ text "The start must be on or before the end." ]

                                  else if not changes then
                                    p [ class "re-meta mt-3 mb-0" ] [ text "This is the range that's published now." ]

                                  else
                                    viewPreview model draft
                                ]
                            , div [ class "modal-footer" ]
                                [ button [ type_ "button", id "publish-cancel", class "btn btn-outline-secondary", onClick ClosePublish ] [ text "Cancel" ]
                                , button
                                    [ type_ "submit"
                                    , id "publish-submit"
                                    , classList [ ( "btn", True ), ( "btn-primary", not hiding ), ( "btn-danger", hiding ) ]
                                    , disabled (not valid || not changes || draft.saving)
                                    ]
                                    [ text
                                        (if valid && not changes then
                                            "No change"

                                         else
                                            publishLabel draft
                                        )
                                    ]
                                ]
                            , span [ tabindex 0, onFocus (FocusId "publish-start") ] []
                            ]
                        ]
                    ]
                , div [ class "modal-backdrop show re-publish-backdrop" ] []
                ]

        Nothing ->
            text ""


viewPreview : Model -> PublishDraft -> Html Msg
viewPreview model draft =
    case draft.preview of
        Just preview ->
            div [ class "re-preview mt-3", attribute "aria-live" "polite" ]
                [ p [ class "mb-2" ]
                    [ text
                        (if preview.shifts_shown + preview.leave_shown == 0 then
                            "Registrars won't see anything new."

                         else
                            "Registrars will start seeing " ++ plural preview.shifts_shown "shift" "shifts" ++ " and " ++ String.fromInt preview.leave_shown ++ " leave."
                        )
                    ]
                , if preview.shifts_hidden + preview.leave_hidden > 0 then
                    p [ class "re-note is-warning" ]
                        [ i [ class "bi bi-exclamation-triangle-fill me-1", attribute "aria-hidden" "true" ] []
                        , text ("This hides " ++ plural preview.shifts_hidden "shift" "shifts" ++ " and " ++ String.fromInt preview.leave_hidden ++ " leave that registrars can see now.")
                        ]

                  else
                    text ""
                , viewHealth model preview
                ]

        Nothing ->
            p [ class "re-meta mt-3 mb-0" ] [ text "Working out what changes…" ]


{-| The state of the days registrars would start seeing, each problem a way back to it in the grid.
-}
viewHealth : Model -> T.PreviewOut -> Html Msg
viewHealth model preview =
    let
        shown =
            model.roster |> Maybe.map (.dates >> List.map day) |> Maybe.withDefault [] |> Set.fromList

        inGrid d =
            Set.member (day d) shown

        limit =
            6

        gapItems =
            List.concatMap
                (\gap ->
                    List.map
                        (\needs ->
                            li []
                                [ problemLink (inGrid gap.date)
                                    (GoToCover gap.date)
                                    [ span [ class "re-problem-when" ] [ text (dayDate gap.date) ]
                                    , text ("needs " ++ needsLabel model (List.map T.shiftTypeToString needs))
                                    ]
                                ]
                        )
                        gap.needs
                )
                preview.gaps

        ruleItems =
            List.map
                (\v ->
                    let
                        first =
                            List.filter inGrid v.dates |> List.head
                    in
                    li []
                        [ problemLink (first /= Nothing)
                            (first |> Maybe.map (\d -> GoToCell ( v.registrar, day d )) |> Maybe.withDefault NoOp)
                            [ span [ class "re-problem-when" ] [ text (registrarName model v.registrar) ]
                            , span [ class "re-clause" ] [ text (nullable v.clause |> Maybe.withDefault "Department rule") ]
                            , text v.message
                            ]
                        ]
                )
                preview.violations

        items =
            gapItems ++ ruleItems

        extra =
            List.length items - limit
    in
    if List.isEmpty items && preview.leave_waiting == 0 then
        if preview.shifts_shown + preview.leave_shown > 0 then
            p [ class "re-note is-ok mb-0" ] [ i [ class "bi bi-check2-circle me-1", attribute "aria-hidden" "true" ] [], text "No cover gaps, rule breaks or undecided leave in the days being published." ]

        else
            text ""

    else
        div [ class "re-health" ]
            [ h3 [ class "re-section-title" ] [ text "Before registrars see these days" ]
            , p [ class "re-meta mt-0 mb-2" ]
                [ text
                    (String.join ", "
                        (List.filter (not << String.isEmpty)
                            [ countPhrase (List.length gapItems) "cover gap" "cover gaps"
                            , countPhrase (List.length ruleItems) "rule break" "rule breaks"
                            , countPhrase preview.leave_waiting "day of leave waiting for a decision" "days of leave waiting for a decision"
                            ]
                        )
                    )
                ]
            , ul [ class "re-problemlist" ] (List.take limit items)
            , if extra > 0 then
                p [ class "re-meta mb-0" ] [ text ("and " ++ String.fromInt extra ++ " more.") ]

              else
                text ""
            ]


countPhrase : Int -> String -> String -> String
countPhrase n one many =
    if n == 0 then
        ""

    else
        plural n one many


problemLink : Bool -> Msg -> List (Html Msg) -> Html Msg
problemLink inGrid msg content =
    if inGrid then
        button [ type_ "button", class "re-problem", onClick msg ] content

    else
        span [ class "re-problem is-static" ] content


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
            div [ class "re-toast is-error", attribute "role" "alert" ]
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


{-| The last change, with a way to undo it. The live region has already announced it.
-}
viewToast : Maybe Toast -> Html Msg
viewToast toast =
    case toast of
        Just t ->
            div [ class "re-toast" ]
                [ span [ class "re-toast-text" ] [ text t.message ]
                , if t.undoable then
                    button [ type_ "button", class "btn btn-sm btn-light", onClick UndoLast ]
                        [ i [ class "bi bi-arrow-counterclockwise me-1", attribute "aria-hidden" "true" ] [], text "Undo" ]

                  else
                    text ""
                , button [ type_ "button", class "btn-close btn-close-white", attribute "aria-label" "Dismiss", onClick (DismissToast t.id) ] []
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


{-| Names who has decided and who is still to: "Chief registrar approved · waiting on the Director of Training."
-}
leaveStateSentence : T.LeaveOut -> String
leaveStateSentence leave =
    let
        reg =
            nullable leave.reg_approved

        dot =
            nullable leave.dot_approved
    in
    if leave.cancelled then
        "Cancelled."

    else
        case ( reg, dot ) of
            ( Just True, Just True ) ->
                "Approved by the chief registrar and the Director of Training."

            ( Just False, _ ) ->
                "Declined by the chief registrar."

            ( _, Just False ) ->
                "Declined by the Director of Training."

            ( Just True, Nothing ) ->
                "Chief registrar approved · waiting on the Director of Training."

            ( Nothing, Just True ) ->
                "Director of Training approved · waiting on the chief registrar."

            ( Nothing, Nothing ) ->
                "Waiting on the chief registrar and the Director of Training."


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


coverId : Date -> String
coverId date =
    "cover-" ++ Date.toIsoString date


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


isProblems : Maybe Popover -> Bool
isProblems popover =
    case popover of
        Just (ProblemsMenu _) ->
            True

        _ ->
            False


{-| `inert` keeps a region out of reach while a popover or dialog is open over it.
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


{-| "2.4": one decimal place, always shown.
-}
formatLoad : Float -> String
formatLoad value =
    let
        tenths =
            round (value * 10)
    in
    String.fromInt (tenths // 10) ++ "." ++ String.fromInt (modBy 10 tenths)


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

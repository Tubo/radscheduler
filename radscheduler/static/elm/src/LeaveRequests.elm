port module LeaveRequests exposing (main)

{-| Where the chief registrar and the Director of Training decide leave, in two steps.

The overview lists every request of the registrars in training, a row each, filtered and sorted: where it
stands, and for one still waiting, what its verdict turns on. Requests with nothing against them can be
approved together from there.

Approval mode then reviews the requests the overview picked out, each beside the roster it affects: the
registrar's own days around it, how many others are on leave, the cover the leave would lose, and the rule
breaks it would cause. The chief registrar and the Director of Training each decide a whole request at once,
or day by day.

The requests come from /api/editor/leave-requests, through the client generated from the API's OpenAPI
schema. Decisions save at once with the same endpoint the roster editor uses, and each can be undone for a
few seconds, the latest first. The filters, and whether approval mode is open, live in the page's address.

Keys in approval mode: j and k move between requests; with focus in a request, a and d approve or decline what
waits in it, and the arrow keys move around its roster, which is a single stop for Tab. Escape goes back to
the overview.

-}

import Browser
import Browser.Dom as Dom
import Browser.Events
import Choice exposing (Choice, choiceDecoder, choiceFor)
import Date exposing (Date)
import Dict exposing (Dict)
import Html exposing (..)
import Html.Attributes exposing (..)
import Html.Events exposing (on, onCheck, onClick, onInput, preventDefaultOn, stopPropagationOn)
import Json.Decode as Decode exposing (Decoder)
import Leave exposing (LeaveState(..), leaveChipClass, leaveChipContent, leaveIcon, leaveState, leaveStateClass, leaveStateName, leaveStateSentence, portionLabel)
import LeaveFilters exposing (Filters)
import OpenApi.Common exposing (Nullable(..))
import Process
import Radscheduler.Api as Api
import Radscheduler.Types as T
import Set exposing (Set)
import Task
import Time


{-| How many requests wait on this user, for the navbar's count.
-}
port waitingChanged : Int -> Cmd msg


{-| The filters and mode as the page's query, to keep in its address.
-}
port replaceQuery : String -> Cmd msg


main : Program Decode.Value Model Msg
main =
    Browser.element
        { init = init
        , update = update
        , view = view
        , subscriptions =
            \model ->
                if model.mode == Review then
                    Browser.Events.onKeyDown shortcutDecoder

                else
                    Sub.none
        }



-- MODEL


type alias Flags =
    { csrfToken : String
    , editorUrl : String
    , shiftTypes : List Choice
    , leaveTypes : List Choice

    -- The decisions this user may make: "reg" (chief registrar) and "dot" (Director of Training).
    , leaveApprovers : List String

    -- The page's query when it opened.
    , query : String
    }


type Mode
    = Overview
    | Review


type Remote a
    = Loading
    | Failed String
    | Loaded a


{-| A decision on some days of one request, by one approver: approve, decline, or back to waiting.
-}
type alias Change =
    { key : Int
    , approver : String
    , leaves : List T.LeaveOut
    , decision : Maybe Bool
    }


{-| Decisions that can be undone for a few seconds: each request's days as they were before them.
-}
type alias Toast =
    { id : Int
    , message : String
    , approver : String
    , before : List ( Int, List T.LeaveOut )
    }


type alias Model =
    { flags : Flags
    , mode : Mode
    , filters : Filters

    -- The overview: a page of rows at a time, the next appended. It keeps the rows it has while a change of
    -- filters loads, and numbers each load, so a slow answer to earlier filters can't replace a later one.
    , overview : Remote T.LeaveOverviewOut
    , overviewAsked : Int
    , refreshing : Bool
    , loadingMore : Bool

    -- Rows ticked to approve together.
    , selected : Set Int

    -- The row opened in place, a shelf under it holding the request with its roster, loaded when opened; and
    -- the number of that load, as for the overview's.
    , shelf : Maybe ( Int, Remote T.LeaveRequestsOut )
    , shelfAsked : Int

    -- Approval mode: the requests the filters match, the first of them drawn, and the one to go to once
    -- they are.
    , data : Remote T.LeaveRequestsOut
    , asked : Int
    , goingTo : Maybe Int

    -- The requests listed, by their first day's id, fixed when the list loads: a request decided here stays
    -- in view, showing its new state, until the list is loaded again. Those with nothing left to decide when
    -- they loaded are settled: read-only until opened for a change.
    , shown : List Int
    , settled : Set Int
    , saving : Set Int

    -- A save that failed, by request: its changes are put back and the reason shown there, with the change to
    -- try again.
    , failed : Dict Int ( String, Change )
    , error : Maybe String

    -- Decisions that can still be undone, the latest first; the toast shows the latest.
    , undos : List Toast
    , toasts : Int

    -- How many requests wait on the user and on anyone, from the server; the navbar's count was last told
    -- `told`.
    , counts : Maybe T.WaitingCountsOut
    , told : Maybe Int

    -- Settled requests opened for a change.
    , changing : Set Int

    -- Requests whose roster is shown, for the Director of Training, who sees a verdict first.
    , expanded : Set Int

    -- The day whose names are shown under a request: the request's key and the day (Rata Die).
    , openDay : Maybe ( Int, Int )

    -- The control in each request's roster that Tab stops at, the request that last had focus, and whether
    -- focus is in it still.
    , gridFocus : Dict Int Spot
    , current : Maybe Int
    , inRequest : Bool

    -- Long rosters scrolled to their end, which lose the fade that says there is more.
    , scrolledEnd : Set Int
    , zone : Time.Zone
    }


type alias ApiError =
    OpenApi.Common.Error Never String


flagsDecoder : Decoder Flags
flagsDecoder =
    Decode.map6 Flags
        (Decode.field "csrfToken" Decode.string)
        (Decode.field "editorUrl" Decode.string)
        (Decode.field "shiftTypes" (Decode.list choiceDecoder))
        (Decode.field "leaveTypes" (Decode.list choiceDecoder))
        (Decode.field "leaveApprovers" (Decode.list Decode.string))
        (Decode.oneOf [ Decode.field "query" Decode.string, Decode.succeed "" ])


emptyModel : Flags -> Model
emptyModel flags =
    let
        ( filters, review ) =
            LeaveFilters.fromQuery (decides flags) flags.query
    in
    { flags = flags
    , mode =
        if review then
            Review

        else
            Overview
    , filters =
        -- Someone who decides nothing has nothing waiting on them.
        if filters.status == "mine" && not (decides flags) then
            { filters | status = "waiting" }

        else
            filters
    , overview = Loading
    , overviewAsked = 0
    , refreshing = False
    , loadingMore = False
    , selected = Set.empty
    , shelf = Nothing
    , shelfAsked = 0
    , data = Loading
    , asked = 0
    , goingTo = Nothing
    , shown = []
    , settled = Set.empty
    , saving = Set.empty
    , failed = Dict.empty
    , error = Nothing
    , undos = []
    , toasts = 0
    , counts = Nothing
    , told = Nothing
    , changing = Set.empty
    , expanded = Set.empty
    , openDay = Nothing
    , gridFocus = Dict.empty
    , current = Nothing
    , inRequest = False
    , scrolledEnd = Set.empty
    , zone = Time.utc
    }


init : Decode.Value -> ( Model, Cmd Msg )
init value =
    case Decode.decodeValue flagsDecoder value of
        Ok flags ->
            let
                model =
                    emptyModel flags

                ( loading, cmd ) =
                    if model.mode == Review then
                        loadReview model

                    else
                        loadOverview model
            in
            ( loading, Cmd.batch [ cmd, loadCounts loading, Task.perform GotZone Time.here ] )

        Err err ->
            let
                model =
                    emptyModel { csrfToken = "", editorUrl = "", shiftTypes = [], leaveTypes = [], leaveApprovers = [], query = "" }
            in
            ( { model | mode = Review, data = Failed ("The page didn't start: " ++ Decode.errorToString err) }, Cmd.none )


{-| The decision a user makes first: the chief registrar's own, or the Director of Training's.
-}
primaryApprover : Flags -> Maybe String
primaryApprover flags =
    if List.member "reg" flags.leaveApprovers then
        Just "reg"

    else if List.member "dot" flags.leaveApprovers then
        Just "dot"

    else
        Nothing


decides : Flags -> Bool
decides flags =
    primaryApprover flags /= Nothing


{-| The Director of Training sees each request's verdict first, and its roster when they ask.
-}
verdictFirst : Flags -> Bool
verdictFirst flags =
    primaryApprover flags == Just "dot"


{-| The filters as the API takes them.
-}
filterParams : Filters -> { status : Maybe String, start : Maybe (Maybe Date), end : Maybe (Maybe Date), years : Maybe String, types : Maybe String, registrar : Maybe (Maybe Int), sort : Maybe String }
filterParams filters =
    { status = Just filters.status
    , start = Just (Result.toMaybe (Date.fromIsoString filters.start))
    , end = Just (Result.toMaybe (Date.fromIsoString filters.end))
    , years = Just (String.join "," (List.map String.fromInt filters.years))
    , types = Just (String.join "," filters.types)
    , registrar = Just filters.registrar
    , sort = Just filters.sort
    }


{-| The overview's first page for the filters, keeping what it shows until it arrives.
-}
loadOverview : Model -> ( Model, Cmd Msg )
loadOverview model =
    let
        asked =
            model.overviewAsked + 1

        p =
            filterParams model.filters
    in
    ( { model
        | overviewAsked = asked
        , refreshing = True
        , loadingMore = False
        , selected = Set.empty
        , overview =
            case model.overview of
                Loaded _ ->
                    model.overview

                _ ->
                    Loading
      }
    , Api.getLeaveOverview
        { authorization = { x_csrftoken = model.flags.csrfToken }
        , toMsg = GotOverview asked False
        , params = { status = p.status, start = p.start, end = p.end, years = p.years, types = p.types, registrar = p.registrar, sort = p.sort, offset = Nothing }
        }
    )


{-| The overview's next page.
-}
loadMore : Model -> ( Model, Cmd Msg )
loadMore model =
    case model.overview of
        Loaded page ->
            let
                p =
                    filterParams model.filters
            in
            ( { model | loadingMore = True }
            , Api.getLeaveOverview
                { authorization = { x_csrftoken = model.flags.csrfToken }
                , toMsg = GotOverview model.overviewAsked True
                , params = { status = p.status, start = p.start, end = p.end, years = p.years, types = p.types, registrar = p.registrar, sort = p.sort, offset = Just (List.length page.rows) }
                }
            )

        _ ->
            ( model, Cmd.none )


{-| Approval mode's requests for the filters, each with its roster.
-}
loadReview : Model -> ( Model, Cmd Msg )
loadReview model =
    let
        asked =
            model.asked + 1
    in
    ( { model | data = Loading, asked = asked, openDay = Nothing, failed = Dict.empty, changing = Set.empty, current = Nothing }
    , Api.getLeaveRequests
        { authorization = { x_csrftoken = model.flags.csrfToken }
        , toMsg = Got asked
        , params = filterParams model.filters
        }
    )


loadCounts : Model -> Cmd Msg
loadCounts model =
    Api.getLeaveCounts { authorization = { x_csrftoken = model.flags.csrfToken }, toMsg = GotCounts }


{-| Keep the filters and the mode in the page's address.
-}
saveQuery : Model -> Cmd Msg
saveQuery model =
    replaceQuery (LeaveFilters.toQuery (decides model.flags) (model.mode == Review) model.filters)


{-| Change the filters: the overview loads again for them, and the address follows.
-}
refilter : (Filters -> Filters) -> Model -> ( Model, Cmd Msg )
refilter change model =
    let
        ( loading, cmd ) =
            loadOverview { model | filters = change model.filters, shelf = Nothing }
    in
    ( loading, Cmd.batch [ cmd, saveQuery loading ] )


toggleIn : comparable -> List comparable -> List comparable
toggleIn item items =
    if List.member item items then
        List.filter ((/=) item) items

    else
        List.sort (item :: items)



-- UPDATE


type Msg
    = GotZone Time.Zone
    | Reload
      -- The overview's filters.
    | SetStatus String
    | SetStart String
    | SetEnd String
    | ToggleYear Int
    | ToggleType String
    | SetRegistrar String
    | SetSort String
    | ClearFilters
    | GotOverview Int Bool (Result ApiError T.LeaveOverviewOut)
    | ShowMore
    | Select Int Bool
    | SelectAll Bool
    | ApproveSelected
      -- A row's shelf: open or close it, load it (again), and Escape in it.
    | ToggleShelf Int
    | LoadShelf Int
    | GotShelf Int Int (Result ApiError T.LeaveRequestsOut)
    | EscapeRequest Int
      -- Approval mode, and the request to go to in it.
    | OpenReview (Maybe Int)
    | CloseReview
    | Got Int (Result ApiError T.LeaveRequestsOut)
    | GotCounts (Result ApiError T.WaitingCountsOut)
      -- A decision, and whether to move on to the next request waiting for this approver.
    | Decide Bool Change
    | Saved Change (List T.LeaveOut) (Result ApiError (List T.LeaveOut))
    | Retry Int
    | Undo
    | DismissToast Int
    | DismissToasts
    | StartChange Int
    | EndChange Int
    | ToggleRoster Int
    | ToggleDay Int Int
    | FocusSpot Int Spot
    | MoveSpot Int Spot
    | EnterRequest Int
    | LeaveRequest
    | Shortcut String
      -- a or d pressed with focus in a request: approve, or decline.
    | RequestKey Int Bool
    | StripScrolled Int Bool
    | NoOp


update : Msg -> Model -> ( Model, Cmd Msg )
update msg model =
    case msg of
        GotZone zone ->
            ( { model | zone = zone }, Cmd.none )

        Reload ->
            if model.mode == Review then
                loadReview { model | error = Nothing }

            else
                loadOverview { model | error = Nothing, overview = Loading }

        SetStatus status ->
            refilter (\f -> { f | status = status }) model

        SetStart start ->
            refilter (\f -> { f | start = start }) model

        SetEnd end ->
            refilter (\f -> { f | end = end }) model

        ToggleYear year ->
            refilter (\f -> { f | years = toggleIn year f.years }) model

        ToggleType type_ ->
            refilter (\f -> { f | types = toggleIn type_ f.types }) model

        SetRegistrar value ->
            refilter (\f -> { f | registrar = String.toInt value }) model

        SetSort sort ->
            refilter (\f -> { f | sort = sort }) model

        ClearFilters ->
            refilter (\_ -> LeaveFilters.defaults (decides model.flags)) model

        GotOverview asked more result ->
            if asked /= model.overviewAsked then
                ( model, Cmd.none )

            else
                case ( result, model.overview ) of
                    ( Ok page, Loaded shown ) ->
                        if more then
                            ( { model | overview = Loaded { page | rows = shown.rows ++ page.rows }, loadingMore = False }, Cmd.none )

                        else
                            ( { model | overview = Loaded page, refreshing = False }, Cmd.none )

                    ( Ok page, _ ) ->
                        ( { model | overview = Loaded page, refreshing = False, loadingMore = False }, Cmd.none )

                    ( Err err, _ ) ->
                        if more then
                            ( { model | loadingMore = False, error = Just ("Couldn't load more requests. " ++ errorMessage err) }, Cmd.none )

                        else
                            ( { model | overview = Failed ("Couldn't load the leave requests. " ++ errorMessage err), refreshing = False }, Cmd.none )

        ShowMore ->
            loadMore model

        Select key on_ ->
            ( { model
                | selected =
                    if on_ then
                        Set.insert key model.selected

                    else
                        Set.remove key model.selected
              }
            , Cmd.none
            )

        SelectAll on_ ->
            ( { model
                | selected =
                    if on_ then
                        Set.fromList (List.map .key (approvable model))

                    else
                        Set.empty
              }
            , Cmd.none
            )

        ApproveSelected ->
            case primaryApprover model.flags of
                Just approver ->
                    let
                        rows =
                            List.filter (\r -> Set.member r.key model.selected) (approvable model)

                        changes =
                            List.map (\r -> { key = r.key, approver = approver, leaves = waitingIn approver r.leaves, decision = Just True }) rows

                        ( decided, cmds ) =
                            List.foldl (\c ( m, cs ) -> decide c m |> Tuple.mapSecond (\cmd -> cmd :: cs)) ( model, [] ) changes

                        days =
                            changes |> List.concatMap .leaves |> List.map (.portion >> weight) |> List.sum

                        message =
                            "Approved "
                                ++ plural (List.length changes) "request" "requests"
                                ++ " ("
                                ++ daysLabel days
                                ++ ") as "
                                ++ approverName approver
                                ++ "."
                    in
                    if List.isEmpty changes then
                        ( model, Cmd.none )

                    else
                        let
                            ( undoable, sleep ) =
                                remember message approver changes { decided | selected = Set.empty }
                        in
                        ( undoable, Cmd.batch (sleep :: cmds) )

                Nothing ->
                    ( model, Cmd.none )

        ToggleShelf key ->
            if Maybe.map Tuple.first model.shelf == Just key then
                ( { model | shelf = Nothing }, Cmd.none )

            else
                update (LoadShelf key) model

        LoadShelf key ->
            let
                asked =
                    model.shelfAsked + 1
            in
            ( { model
                | shelf = Just ( key, Loading )
                , shelfAsked = asked
                , failed = Dict.remove key model.failed

                -- The Director of Training, who sees verdicts first in review, opened this one to see it.
                , expanded = Set.insert key model.expanded
              }
            , Api.getLeaveRequest
                { authorization = { x_csrftoken = model.flags.csrfToken }
                , toMsg = GotShelf asked key
                , params = { key = key }
                }
            )

        GotShelf asked key result ->
            if asked /= model.shelfAsked then
                ( model, Cmd.none )

            else
                case result of
                    Ok data ->
                        ( { model
                            | shelf = Just ( key, Loaded data )
                            , settled =
                                if List.all (\r -> List.isEmpty (waitingIn "reg" r.leaves ++ waitingIn "dot" r.leaves)) data.requests then
                                    Set.insert key model.settled

                                else
                                    Set.remove key model.settled
                          }
                        , Cmd.none
                        )

                    Err err ->
                        ( { model | shelf = Just ( key, Failed ("Couldn't load this request. " ++ errorMessage err) ) }, Cmd.none )

        EscapeRequest key ->
            if model.mode == Overview && Maybe.map Tuple.first model.shelf == Just key then
                ( { model | shelf = Nothing }, Task.attempt (\_ -> NoOp) (Dom.focus (rowId key)) )

            else
                ( model, Cmd.none )

        OpenReview key ->
            let
                ( loading, cmd ) =
                    loadReview { model | mode = Review, goingTo = key, undos = [] }
            in
            ( loading, Cmd.batch [ cmd, saveQuery loading, Task.attempt (\_ -> NoOp) (Dom.setViewport 0 0) ] )

        CloseReview ->
            let
                ( loading, cmd ) =
                    loadOverview { model | mode = Overview, data = Loading, undos = [] }
            in
            ( loading, Cmd.batch [ cmd, saveQuery loading ] )

        Got asked result ->
            if asked /= model.asked then
                ( model, Cmd.none )

            else
                case result of
                    Ok data ->
                        let
                            loaded =
                                { model
                                    | data = Loaded data
                                    , shown = List.map requestKey data.requests
                                    , settled =
                                        data.requests
                                            |> List.filter (\r -> List.isEmpty (waitingIn "reg" r.leaves ++ waitingIn "dot" r.leaves))
                                            |> List.map requestKey
                                            |> Set.fromList
                                    , goingTo = Nothing
                                }
                        in
                        ( loaded
                        , case model.goingTo of
                            Just key ->
                                goTo key

                            Nothing ->
                                Cmd.none
                        )

                    Err err ->
                        ( { model | data = Failed ("Couldn't load the leave requests. " ++ errorMessage err) }, Cmd.none )

        GotCounts result ->
            case result of
                Ok counts ->
                    let
                        counted =
                            { model | counts = Just counts }
                    in
                    case nullable counts.mine of
                        Just n ->
                            if model.told /= Just n then
                                ( { counted | told = Just n }, waitingChanged n )

                            else
                                ( counted, Cmd.none )

                        Nothing ->
                            ( counted, Cmd.none )

                Err _ ->
                    ( model, Cmd.none )

        Decide advance change ->
            if List.isEmpty change.leaves then
                ( model, Cmd.none )

            else
                let
                    ( decided, cmd ) =
                        decide change model

                    ( undoable, sleep ) =
                        remember (changeMessage decided change) change.approver [ change ] decided
                in
                ( undoable
                , Cmd.batch
                    [ cmd
                    , sleep
                    , if advance then
                        advanceFrom change.key change.approver undoable

                      else
                        Cmd.none
                    ]
                )

        Saved change before result ->
            let
                done =
                    { model | saving = Set.diff model.saving (Set.fromList (List.map .id change.leaves)) }
            in
            case result of
                Ok saved ->
                    ( { done
                        | data = replaceLeaves saved done.data
                        , shelf = Maybe.map (Tuple.mapSecond (replaceLeaves saved)) done.shelf
                        , overview = replaceRowLeaves saved done.overview
                      }
                    , loadCounts done
                    )

                Err err ->
                    ( { done
                        | data = replaceLeaves before done.data
                        , shelf = Maybe.map (Tuple.mapSecond (replaceLeaves before)) done.shelf
                        , overview = replaceRowLeaves before done.overview
                        , failed = Dict.insert change.key ( "Couldn't save the decision, so it's been put back. " ++ errorMessage err, change ) done.failed
                        , undos = List.filter (\t -> not (List.any (Tuple.first >> (==) change.key) t.before)) done.undos
                        , error =
                            if done.mode == Overview then
                                Just ("Couldn't save a decision, so it's been put back. " ++ errorMessage err)

                            else
                                done.error
                      }
                    , Cmd.none
                    )

        Retry key ->
            case Dict.get key model.failed of
                Just ( _, change ) ->
                    decide change model

                Nothing ->
                    ( model, Cmd.none )

        Undo ->
            case model.undos of
                toast :: rest ->
                    -- Put each day back to the decision it had, grouping each request's days that had the same one.
                    let
                        changes =
                            toast.before
                                |> List.concatMap
                                    (\( key, leaves ) ->
                                        leaves
                                            |> List.foldl
                                                (\leave acc ->
                                                    Dict.update (decisionKey (decisionOf toast.approver leave)) (\l -> Just (Maybe.withDefault [] l ++ [ leave ])) acc
                                                )
                                                Dict.empty
                                            |> Dict.values
                                            |> List.filterMap
                                                (\group ->
                                                    List.head group
                                                        |> Maybe.map (\first -> { key = key, approver = toast.approver, leaves = group, decision = decisionOf toast.approver first })
                                                )
                                    )

                        ( reverted, cmds ) =
                            List.foldl (\c ( m, cs ) -> decide c m |> Tuple.mapSecond (\cmd -> cmd :: cs)) ( { model | undos = rest }, [] ) changes
                    in
                    ( reverted, Cmd.batch cmds )

                [] ->
                    ( model, Cmd.none )

        DismissToast id ->
            ( { model | undos = List.filter (\t -> t.id /= id) model.undos }, Cmd.none )

        DismissToasts ->
            ( { model | undos = [] }, Cmd.none )

        StartChange key ->
            ( { model | changing = Set.insert key model.changing }
            , Task.attempt (\_ -> NoOp) (Dom.focus (requestId key ++ "-change"))
            )

        EndChange key ->
            ( { model | changing = Set.remove key model.changing }
            , Task.attempt (\_ -> NoOp) (Dom.focus (requestId key ++ "-start-change"))
            )

        ToggleRoster key ->
            ( { model | expanded = toggle key model.expanded }, Cmd.none )

        ToggleDay key d ->
            ( { model
                | openDay =
                    if model.openDay == Just ( key, d ) then
                        Nothing

                    else
                        Just ( key, d )
              }
            , Cmd.none
            )

        FocusSpot key spot ->
            ( { model | gridFocus = Dict.insert key spot model.gridFocus, current = Just key }, Cmd.none )

        MoveSpot key spot ->
            ( { model | gridFocus = Dict.insert key spot model.gridFocus }
            , Task.attempt (\_ -> NoOp) (Dom.focus (spotId key spot))
            )

        EnterRequest key ->
            ( { model | current = Just key, inRequest = True }, Cmd.none )

        LeaveRequest ->
            ( { model | inRequest = False }, Cmd.none )

        Shortcut key ->
            shortcut key model

        RequestKey key approve ->
            case ( requestFor model key, primaryApprover model.flags ) of
                ( Just ( _, request ), Just approver ) ->
                    if not (editable model key) then
                        ( model, Cmd.none )

                    else if approve && riskOf model request /= Nothing then
                        -- Approving despite a rule break or lost cover takes the button, which says so.
                        ( model, Task.attempt (\_ -> NoOp) (Dom.focus (requestId key ++ "-approve")) )

                    else
                        update (Decide True { key = key, approver = approver, leaves = waitingFor approver request, decision = Just approve }) model

                _ ->
                    ( model, Cmd.none )

        StripScrolled key atEnd ->
            ( { model
                | scrolledEnd =
                    if atEnd then
                        Set.insert key model.scrolledEnd

                    else
                        Set.remove key model.scrolledEnd
              }
            , Cmd.none
            )

        NoOp ->
            ( model, Cmd.none )


{-| Keep decisions to undo for a few seconds, under a message saying what they did.
-}
remember : String -> String -> List Change -> Model -> ( Model, Cmd Msg )
remember message approver changes model =
    let
        id =
            model.toasts + 1

        toast =
            { id = id, message = message, approver = approver, before = List.map (\c -> ( c.key, c.leaves )) changes }
    in
    ( { model | undos = List.take 5 (toast :: model.undos), toasts = id }
    , Process.sleep 8000 |> Task.perform (\_ -> DismissToast id)
    )


{-| Record a decision at once and send it; the days as they were come back if it fails.
-}
decide : Change -> Model -> ( Model, Cmd Msg )
decide change model =
    let
        ids =
            List.map .id change.leaves

        value =
            case change.decision of
                Just b ->
                    Present b

                Nothing ->
                    Null

        apply leave =
            if List.member leave.id ids then
                if change.approver == "reg" then
                    { leave | reg_approved = value }

                else
                    { leave | dot_approved = value }

            else
                leave
    in
    ( { model
        | data = mapLeaves apply model.data
        , shelf = Maybe.map (Tuple.mapSecond (mapLeaves apply)) model.shelf
        , overview = mapRowLeaves apply model.overview
        , saving = Set.union model.saving (Set.fromList ids)
        , failed = Dict.remove change.key model.failed
      }
    , Api.changeLeaves
        { authorization = { x_csrftoken = model.flags.csrfToken }
        , toMsg = Saved change change.leaves
        , body =
            { ids = ids
            , reg_approved = when (change.approver == "reg") value
            , dot_approved = when (change.approver == "dot") value
            , microster = Nothing
            , cancelled = Nothing
            }
        }
    )


{-| "Approved 15 days of Junaid Burney's annual leave as chief registrar.", "Set Thu 28 Jan of Junaid Burney's
annual leave back to waiting for the chief registrar."
-}
changeMessage : Model -> Change -> String
changeMessage model change =
    let
        what =
            case change.leaves of
                [ one ] ->
                    Date.format "EEE d MMM" one.date

                leaves ->
                    plural (List.length leaves) "day" "days"

        whose =
            requestFor model change.key
                |> Maybe.map (\( looks, request ) -> registrarName looks request.registrar ++ "'s " ++ String.toLower (requestTypeName model request))
                |> Maybe.withDefault "the leave"
    in
    case change.decision of
        Just True ->
            "Approved " ++ what ++ " of " ++ whose ++ " as " ++ approverName change.approver ++ "."

        Just False ->
            "Declined " ++ what ++ " of " ++ whose ++ " as " ++ approverName change.approver ++ "."

        Nothing ->
            "Set " ++ what ++ " of " ++ whose ++ " back to waiting for the " ++ approverName change.approver ++ "."


{-| j and k move between requests; from outside them, back to the one last used, or the first.
-}
shortcut : String -> Model -> ( Model, Cmd Msg )
shortcut key model =
    let
        keys =
            listedKeys model

        index =
            model.current |> Maybe.andThen (\k -> indexOf k keys)

        go i =
            case List.head (List.drop i keys) of
                Just k ->
                    ( { model | current = Just k }, goTo k )

                Nothing ->
                    ( model, Cmd.none )
    in
    case ( key, index, model.inRequest ) of
        ( "Escape", _, _ ) ->
            update CloseReview model

        ( _, Just i, False ) ->
            go i

        ( "j", _, _ ) ->
            go (Maybe.map ((+) 1) index |> Maybe.withDefault 0)

        ( "k", _, _ ) ->
            go (Maybe.map (\i -> Basics.max 0 (i - 1)) index |> Maybe.withDefault 0)

        _ ->
            ( model, Cmd.none )


{-| Focus a request and scroll it to the top, just under the bar of tabs.
-}
goTo : Int -> Cmd Msg
goTo key =
    Task.map3 (\target bar viewport -> ( target, bar, viewport ))
        (Dom.getElement (requestId key))
        (Dom.getElement "lr-bar")
        Dom.getViewport
        |> Task.andThen
            (\( target, bar, viewport ) ->
                let
                    -- The bar sticks over the list from 48rem wide.
                    covered =
                        if viewport.viewport.width >= 768 then
                            bar.element.height

                        else
                            0
                in
                -- Focus first: focus landing during the (smooth) scroll would cut it short.
                Dom.focus (requestId key)
                    |> Task.andThen (\_ -> Dom.setViewport viewport.viewport.x (target.element.y - covered - 12))
            )
        |> Task.attempt (\_ -> NoOp)


{-| After deciding a request, on to the next one still waiting for the approver; or, with none left, keep focus
in this one, whose buttons have gone.
-}
advanceFrom : Int -> String -> Model -> Cmd Msg
advanceFrom key approver model =
    let
        keys =
            listedKeys model

        later =
            case indexOf key keys of
                Just i ->
                    List.drop (i + 1) keys

                Nothing ->
                    []

        waiting k =
            requestFor model k |> Maybe.map (\( _, r ) -> not (List.isEmpty (waitingFor approver r))) |> Maybe.withDefault False
    in
    case List.head (List.filter waiting later) of
        Just next ->
            goTo next

        Nothing ->
            Task.attempt (\_ -> NoOp) (Dom.focus (requestId key))


{-| j and k anywhere on the page in approval mode, unless typing in a field or holding a modifier, and Escape
back to the overview. They only move focus or leave; the keys that decide work only with focus in a request.
-}
shortcutDecoder : Decoder Msg
shortcutDecoder =
    Decode.map5
        (\key ctrl meta alt tag ->
            if ctrl || meta || alt || List.member tag [ "INPUT", "TEXTAREA", "SELECT" ] || not (List.member key [ "j", "k", "Escape" ]) then
                NoOp

            else
                Shortcut key
        )
        (Decode.field "key" Decode.string)
        (Decode.field "ctrlKey" Decode.bool)
        (Decode.field "metaKey" Decode.bool)
        (Decode.field "altKey" Decode.bool)
        (Decode.oneOf [ Decode.at [ "target", "tagName" ] Decode.string, Decode.succeed "" ])


{-| a and d inside a request, and Escape, which closes the overview's shelf.
-}
requestKeyDecoder : Int -> Decoder Msg
requestKeyDecoder key =
    Decode.map4
        (\k ctrl meta alt ->
            if ctrl || meta || alt then
                NoOp

            else
                case k of
                    "a" ->
                        RequestKey key True

                    "d" ->
                        RequestKey key False

                    "Escape" ->
                        EscapeRequest key

                    _ ->
                        NoOp
        )
        (Decode.field "key" Decode.string)
        (Decode.field "ctrlKey" Decode.bool)
        (Decode.field "metaKey" Decode.bool)
        (Decode.field "altKey" Decode.bool)


when : Bool -> a -> Maybe a
when condition value =
    if condition then
        Just value

    else
        Nothing


toggle : comparable -> Set comparable -> Set comparable
toggle item set =
    if Set.member item set then
        Set.remove item set

    else
        Set.insert item set


decisionKey : Maybe Bool -> Int
decisionKey decision =
    case decision of
        Just True ->
            1

        Just False ->
            0

        Nothing ->
            -1


{-| The keys in the order they are drawn, groups included.
-}
listedKeys : Model -> List Int
listedKeys model =
    case model.data of
        Loaded data ->
            groupsFor model data |> List.concatMap (Tuple.second >> List.map requestKey)

        _ ->
            []


{-| A request on the page, in approval mode's list or the overview's shelf.
-}
requestFor : Model -> Int -> Maybe ( Lookups, T.LeaveRequestOut )
requestFor model key =
    let
        find remote =
            case remote of
                Loaded data ->
                    data.requests |> List.filter (\r -> requestKey r == key) |> List.head |> Maybe.map (Tuple.pair (lookups data))

                _ ->
                    Nothing
    in
    case find model.data of
        Just found ->
            Just found

        Nothing ->
            model.shelf |> Maybe.andThen (Tuple.second >> find)


mapLeaves : (T.LeaveOut -> T.LeaveOut) -> Remote T.LeaveRequestsOut -> Remote T.LeaveRequestsOut
mapLeaves f remote =
    case remote of
        Loaded data ->
            Loaded { data | requests = List.map (\r -> { r | leaves = List.map f r.leaves }) data.requests }

        _ ->
            remote


replaceLeaves : List T.LeaveOut -> Remote T.LeaveRequestsOut -> Remote T.LeaveRequestsOut
replaceLeaves leaves =
    mapLeaves (replacing leaves)


mapRowLeaves : (T.LeaveOut -> T.LeaveOut) -> Remote T.LeaveOverviewOut -> Remote T.LeaveOverviewOut
mapRowLeaves f remote =
    case remote of
        Loaded page ->
            Loaded { page | rows = List.map (\r -> { r | leaves = List.map f r.leaves }) page.rows }

        _ ->
            remote


replaceRowLeaves : List T.LeaveOut -> Remote T.LeaveOverviewOut -> Remote T.LeaveOverviewOut
replaceRowLeaves leaves =
    mapRowLeaves (replacing leaves)


replacing : List T.LeaveOut -> T.LeaveOut -> T.LeaveOut
replacing leaves =
    let
        byId =
            Dict.fromList (List.map (\l -> ( l.id, l )) leaves)
    in
    \l -> Dict.get l.id byId |> Maybe.withDefault l


errorMessage : ApiError -> String
errorMessage error =
    case error of
        OpenApi.Common.BadUrl url ->
            "Bad URL: " ++ url

        OpenApi.Common.Timeout ->
            "The server took too long to respond."

        OpenApi.Common.NetworkError ->
            "Couldn't reach the server. Check your connection."

        OpenApi.Common.KnownBadStatus _ body ->
            never body

        OpenApi.Common.UnknownBadStatus metadata _ ->
            statusMessage metadata.statusCode

        OpenApi.Common.BadErrorBody metadata _ ->
            statusMessage metadata.statusCode

        OpenApi.Common.BadBody _ _ ->
            "The server sent a response the page didn't understand. Reload the page."


statusMessage : Int -> String
statusMessage status =
    case status of
        401 ->
            "You've been signed out. Reload the page to sign in again."

        403 ->
            "Your account can't make this decision; ask the chief registrar."

        _ ->
            "Something went wrong on the server (" ++ String.fromInt status ++ "). Try again."



-- REQUESTS


requestKey : T.LeaveRequestOut -> Int
requestKey request =
    List.head request.leaves |> Maybe.map .id |> Maybe.withDefault 0


decisionOf : String -> T.LeaveOut -> Maybe Bool
decisionOf approver leave =
    nullable
        (if approver == "reg" then
            leave.reg_approved

         else
            leave.dot_approved
        )


approverName : String -> String
approverName approver =
    if approver == "reg" then
        "chief registrar"

    else
        "Director of Training"


{-| Leave that takes the registrar off the roster: not cancelled or declined.
-}
isActive : T.LeaveOut -> Bool
isActive leave =
    case leaveState leave of
        Cancelled ->
            False

        Declined ->
            False

        _ ->
            True


{-| The days still waiting for an approver: not declined by either, and not yet decided by them.
-}
waitingFor : String -> T.LeaveRequestOut -> List T.LeaveOut
waitingFor approver request =
    waitingIn approver request.leaves


waitingIn : String -> List T.LeaveOut -> List T.LeaveOut
waitingIn approver =
    List.filter (\l -> isActive l && decisionOf approver l == Nothing)


{-| Whether the user can change a request here: one with something to decide when it loaded, or a settled one
they opened to change.
-}
editable : Model -> Int -> Bool
editable model key =
    not (Set.member key model.settled) || Set.member key model.changing


{-| The overview's rows that can be approved together: waiting on the user, checked, and with nothing against
them (no rule break, no cover lost, no busy day). Days not rostered yet don't stop it: leave is mostly given
before the roster is built around it.
-}
approvable : Model -> List T.RequestRowOut
approvable model =
    case ( model.overview, primaryApprover model.flags ) of
        ( Loaded page, Just approver ) ->
            List.filter
                (\row ->
                    not (List.isEmpty (waitingIn approver row.leaves))
                        && not (List.any (\l -> Set.member l.id model.saving) row.leaves)
                        && (nullable row.checks |> Maybe.map (\c -> checksLevel c == Clear || checksLevel c == Unchecked) |> Maybe.withDefault False)
                )
                page.rows

        _ ->
            []


{-| "Annual leave", "Lieu day"
-}
requestTypeName : { a | flags : Flags } -> T.LeaveRequestOut -> String
requestTypeName model request =
    case List.head request.leaves of
        Just leave ->
            leaveName (choiceFor model.flags.leaveTypes (T.leaveTypeToString leave.type_))

        Nothing ->
            "Leave"


leaveName : Choice -> String
leaveName choice =
    if String.contains "day" (String.toLower choice.label) || String.contains "leave" (String.toLower choice.label) then
        choice.label

    else
        choice.label ++ " leave"


shiftName : { a | flags : Flags } -> T.ShiftType -> String
shiftName model shiftType =
    (choiceFor model.flags.shiftTypes (T.shiftTypeToString shiftType)).label


{-| A day of leave counts as one, or a half for a morning or an afternoon.
-}
weight : String -> Float
weight portion =
    if portion == "ALL" then
        1

    else
        0.5


{-| "2,121"
-}
thousands : Int -> String
thousands n =
    let
        digits =
            String.fromInt n
    in
    if String.length digits <= 3 then
        digits

    else
        thousands (n // 1000) ++ "," ++ String.padLeft 3 '0' (String.fromInt (modBy 1000 n))


pluralWord : Int -> String -> String -> String
pluralWord n one many =
    if n == 1 then
        one

    else
        many


capitalise : String -> String
capitalise words =
    String.toUpper (String.left 1 words) ++ String.dropLeft 1 words


{-| "2½"
-}
formatDays : Float -> String
formatDays n =
    let
        whole =
            floor n

        half =
            n - toFloat whole >= 0.5
    in
    case ( whole, half ) of
        ( 0, True ) ->
            "½"

        ( _, True ) ->
            String.fromInt whole ++ "½"

        _ ->
            String.fromInt whole


daysLabel : Float -> String
daysLabel n =
    formatDays n
        ++ (if n > 1 then
                " days"

            else
                " day"
           )


{-| Everyone on leave on a day, this request's active days included, counted in halves.
-}
awayOn : T.LeaveRequestOut -> Int -> Float
awayOn request d =
    (request.away |> List.filter (\a -> Date.toRataDie a.date == d) |> List.map (.portion >> weight) |> List.sum)
        + (request.leaves |> List.filter (\l -> Date.toRataDie l.date == d && isActive l) |> List.map (.portion >> weight) |> List.sum)


{-| The days the request would take, as Rata Die: those not cancelled or declined.
-}
activeDays : T.LeaveRequestOut -> List Int
activeDays request =
    request.leaves |> List.filter isActive |> List.map (.date >> Date.toRataDie) |> unique


{-| The cover the leave would lose: "Swing on Thu 28 Jan".
-}
lostCover : { a | flags : Flags } -> T.LeaveRequestOut -> List String
lostCover model request =
    activeDays request
        |> List.concatMap
            (\d ->
                dayInfo request d
                    |> Maybe.map .lost
                    |> Maybe.withDefault []
                    |> List.map (\need -> String.join " or " (List.map (shiftName model) need) ++ " on " ++ Date.format "EEE d MMM" (Date.fromRataDie d))
            )


{-| What giving the leave would cost, if anything: "1 rule break", "lost cover", "2 rule breaks and lost cover".
-}
riskOf : { a | flags : Flags } -> T.LeaveRequestOut -> Maybe String
riskOf model request =
    case ( List.length request.violations, List.isEmpty (lostCover model request) ) of
        ( 0, True ) ->
            Nothing

        ( 0, False ) ->
            Just "lost cover"

        ( n, True ) ->
            Just (plural n "rule break" "rule breaks")

        ( n, False ) ->
            Just (plural n "rule break" "rule breaks" ++ " and lost cover")


dayInfo : T.LeaveRequestOut -> Int -> Maybe T.RequestDayOut
dayInfo request d =
    request.days |> List.filter (\i -> Date.toRataDie i.date == d) |> List.head


{-| 0 for nobody on leave, then 1 to 4 for under 10%, 10–20%, 20–30% and 30% or more of the roster.
-}
heatStep : Float -> Int -> Int
heatStep count rostered =
    let
        share =
            count / toFloat (Basics.max 1 rostered)
    in
    if count == 0 then
        0

    else if share < 0.1 then
        1

    else if share < 0.2 then
        2

    else if share < 0.3 then
        3

    else
        4



-- GRID FOCUS


{-| A control in a request's roster: its row (0 chief registrar, 1 Director of Training, 2 on leave) and column
(two per day: approve, then decline; the day's count takes the first).
-}
type alias Spot =
    ( Int, Int )


spotId : Int -> Spot -> String
spotId key ( row, col ) =
    "spot-" ++ String.fromInt key ++ "-" ++ String.fromInt row ++ "-" ++ String.fromInt col


{-| A row of the overview, by its request's key: the name that opens its shelf.
-}
rowId : Int -> String
rowId key =
    "row-" ++ String.fromInt key


requestId : Int -> String
requestId key =
    "request-" ++ String.fromInt key


{-| The controls a request's roster offers this user, by row, in column order.
-}
spots : Model -> T.LeaveRequestOut -> List Spot
spots model request =
    let
        key =
            requestKey request

        asked =
            List.map (\l -> Date.toRataDie l.date) request.leaves

        decisionSpots row approver =
            if List.member approver model.flags.leaveApprovers && editable model key then
                request.dates
                    |> List.indexedMap Tuple.pair
                    |> List.filter (\( _, date ) -> List.member (Date.toRataDie date) asked)
                    |> List.concatMap (\( i, _ ) -> [ ( row, i * 2 ), ( row, i * 2 + 1 ) ])

            else
                []
    in
    decisionSpots 0 "reg" ++ decisionSpots 1 "dot" ++ List.indexedMap (\i _ -> ( 2, i * 2 )) request.dates


{-| The control Tab stops at in a request's roster: the last one used, or the first.
-}
tabStop : Model -> T.LeaveRequestOut -> Maybe Spot
tabStop model request =
    let
        all =
            spots model request
    in
    case Dict.get (requestKey request) model.gridFocus of
        Just spot ->
            if List.member spot all then
                Just spot

            else
                List.head all

        Nothing ->
            List.head all


{-| Arrow keys within a roster: along a row, or to the nearest control in the row above or below.
-}
arrowDecoder : Model -> T.LeaveRequestOut -> Spot -> Decoder ( Msg, Bool )
arrowDecoder model request ( row, col ) =
    let
        all =
            spots model request

        inRow r =
            List.filter (\( r2, _ ) -> r2 == r) all

        rows =
            all |> List.map Tuple.first |> Set.fromList |> Set.toList

        nearest r =
            inRow r |> List.sortBy (\( _, c ) -> abs (c - col)) |> List.head

        along step =
            let
                candidates =
                    inRow row |> List.filter (\( _, c ) -> step * (c - col) > 0) |> List.sortBy (\( _, c ) -> step * c)
            in
            List.head candidates

        across step =
            rows |> List.filter (\r -> step * (r - row) > 0) |> List.sortBy (\r -> step * r) |> List.head |> Maybe.andThen nearest

        move target =
            case target of
                Just spot ->
                    Decode.succeed ( MoveSpot (requestKey request) spot, True )

                Nothing ->
                    Decode.succeed ( NoOp, True )
    in
    Decode.field "key" Decode.string
        |> Decode.andThen
            (\key ->
                case key of
                    "ArrowRight" ->
                        move (along 1)

                    "ArrowLeft" ->
                        move (along -1)

                    "ArrowDown" ->
                        move (across 1)

                    "ArrowUp" ->
                        move (across -1)

                    "Home" ->
                        move (List.head (inRow row))

                    "End" ->
                        move (List.head (List.reverse (inRow row)))

                    _ ->
                        Decode.fail "not an arrow"
            )


{-| A roster control's focus behaviour: one stop for Tab, arrow keys inside.
-}
spotAttributes : Model -> T.LeaveRequestOut -> Spot -> List (Attribute Msg)
spotAttributes model request spot =
    let
        key =
            requestKey request
    in
    [ id (spotId key spot)
    , tabindex
        (if tabStop model request == Just spot then
            0

         else
            -1
        )
    , on "focus" (Decode.succeed (FocusSpot key spot))
    , preventDefaultOn "keydown" (arrowDecoder model request spot)
    ]



-- VIEW


view : Model -> Html Msg
view model =
    div [ class "leave-requests", classList [ ( "is-review", model.mode == Review ) ] ]
        [ header [ class "lr-head" ]
            [ h1 [] [ text "Leave requests" ]
            , p [ class "lr-role" ] [ text (roleLine model.flags) ]
            , viewHelp model
            ]
        , case model.mode of
            Overview ->
                viewOverview model

            Review ->
                viewReview model
        , div [ class "re-toasts lr-toasts", attribute "aria-live" "polite" ] [ viewToast model.undos ]
        ]


viewError : Model -> Html Msg
viewError model =
    case model.error of
        Just message ->
            div [ class "re-note is-error lr-alert", attribute "role" "alert" ] [ text message ]

        Nothing ->
            text ""



-- OVERVIEW


viewOverview : Model -> Html Msg
viewOverview model =
    div [ class "lr-overview" ]
        [ viewFilters model
        , viewOverviewBar model
        , viewError model
        , case model.overview of
            Loading ->
                p [ class "lr-loading", attribute "role" "status" ]
                    [ span [ class "spinner-border spinner-border-sm", attribute "aria-hidden" "true" ] []
                    , text "Loading leave requests"
                    ]

            Failed message ->
                div [ class "re-note is-error lr-alert", attribute "role" "alert" ]
                    [ text message
                    , button [ type_ "button", class "re-btn", onClick Reload ] [ text "Try again" ]
                    ]

            Loaded page ->
                if List.isEmpty page.rows then
                    viewOverviewEmpty model

                else
                    div [ classList [ ( "is-refreshing", model.refreshing ) ] ]
                        [ viewTable model page
                        , if List.length page.rows < page.total then
                            div [ class "lr-more" ]
                                [ button [ type_ "button", class "re-btn", disabled model.loadingMore, onClick ShowMore ]
                                    [ text
                                        ("Show more ("
                                            ++ thousands (List.length page.rows)
                                            ++ " of "
                                            ++ thousands page.total
                                            ++ " shown)"
                                        )
                                    ]
                                ]

                          else
                            text ""
                        ]
        ]


{-| Where the requests stand, then when, whose and what, and the order.
-}
viewFilters : Model -> Html Msg
viewFilters model =
    let
        filters =
            model.filters

        count status =
            case ( status, model.counts ) of
                ( "mine", Just counts ) ->
                    nullable counts.mine

                ( "waiting", Just counts ) ->
                    Just counts.all

                _ ->
                    Nothing

        statusButton status =
            button
                [ type_ "button"
                , class "lr-tab"
                , classList [ ( "is-on", filters.status == status ) ]
                , attribute "aria-pressed" (boolString (filters.status == status))
                , onClick (SetStatus status)
                ]
                (text (LeaveFilters.statusLabel status)
                    :: (case count status of
                            Just n ->
                                [ span [ class "lr-tabcount" ] [ text (String.fromInt n) ] ]

                            Nothing ->
                                []
                       )
                )

        registrars =
            case model.overview of
                Loaded page ->
                    page.registrars

                _ ->
                    []

        years =
            registrars |> List.filterMap (.year >> nullable) |> unique |> List.sort

        chip pressed label msg =
            button [ type_ "button", class "lr-chip", classList [ ( "is-on", pressed ) ], attribute "aria-pressed" (boolString pressed), onClick msg ] [ text label ]

        field label control =
            div [ class "lr-field" ] [ label, control ]

        dateInput id_ value_ toMsg =
            input
                [ type_ "date"
                , id id_
                , class "re-input"
                , value value_
                , on "change" (Decode.map toMsg (Decode.at [ "target", "value" ] Decode.string))
                ]
                []
    in
    section [ class "lr-filters", attribute "aria-label" "Which requests" ]
        [ div [ class "lr-tabs lr-statuses", attribute "role" "group", attribute "aria-label" "Where they stand" ]
            (List.map statusButton
                ((if decides model.flags then
                    [ "mine" ]

                  else
                    []
                 )
                    ++ [ "waiting", "approved", "declined", "cancelled", "any" ]
                )
            )
        , div [ class "lr-filter-row" ]
            [ div [ class "lr-field" ]
                [ span [ class "lr-field-label", id "lr-dates-label" ] [ text "Leave between" ]
                , div [ class "lr-dates", attribute "role" "group", attribute "aria-labelledby" "lr-dates-label" ]
                    [ label [ class "visually-hidden", for "lr-start" ] [ text "From" ]
                    , dateInput "lr-start" filters.start SetStart
                    , span [ class "lr-dates-and", attribute "aria-hidden" "true" ] [ text "and" ]
                    , label [ class "visually-hidden", for "lr-end" ] [ text "To" ]
                    , dateInput "lr-end" filters.end SetEnd
                    ]
                ]
            , if List.isEmpty years then
                text ""

              else
                field (span [ class "lr-field-label", id "lr-years-label" ] [ text "Year" ])
                    (div [ class "lr-chips-row", attribute "role" "group", attribute "aria-labelledby" "lr-years-label" ]
                        (List.map (\y -> chip (List.member y filters.years) (String.fromInt y) (ToggleYear y)) years)
                    )
            , field (span [ class "lr-field-label", id "lr-types-label" ] [ text "Type" ])
                (div [ class "lr-chips-row", attribute "role" "group", attribute "aria-labelledby" "lr-types-label" ]
                    (List.map (\c -> chip (List.member c.value filters.types) c.label (ToggleType c.value)) model.flags.leaveTypes)
                )
            , field (label [ class "lr-field-label", for "lr-registrar" ] [ text "Registrar" ])
                (select [ id "lr-registrar", class "re-input", onInput SetRegistrar ]
                    (option [ value "", selected (filters.registrar == Nothing) ] [ text "Everyone in training" ]
                        :: (registrars
                                |> List.sortBy (.name >> String.toLower)
                                |> List.map
                                    (\r ->
                                        option [ value (String.fromInt r.id), selected (filters.registrar == Just r.id) ]
                                            [ text (r.name ++ (nullable r.year |> Maybe.map (\y -> ", year " ++ String.fromInt y) |> Maybe.withDefault "")) ]
                                    )
                           )
                    )
                )
            , if LeaveFilters.isDefault (decides model.flags) filters then
                text ""

              else
                button [ type_ "button", class "re-btn re-btn--quiet lr-clear", onClick ClearFilters ] [ text "Clear filters" ]
            ]
        ]


{-| How many match, and what to do with them: review them, or approve those ticked.
-}
viewOverviewBar : Model -> Html Msg
viewOverviewBar model =
    let
        total =
            case model.overview of
                Loaded page ->
                    Just page.total

                _ ->
                    Nothing

        picked =
            List.filter (\r -> Set.member r.key model.selected) (approvable model)

        pickedDays =
            picked |> List.concatMap .leaves |> List.filter isActive |> List.map (.portion >> weight) |> List.sum
    in
    div [ class "lr-bar lr-overview-bar", id "lr-bar" ]
        [ div [ class "lr-matches", attribute "aria-live" "polite" ]
            [ case total of
                Just n ->
                    strong [] [ text (thousands n ++ " " ++ pluralWord n "request" "requests") ]

                Nothing ->
                    text ""
            , label [ class "lr-sort" ]
                [ span [ class "visually-hidden" ] [ text "Sort" ]
                , select [ class "re-input", onInput SetSort, attribute "aria-label" "Sort" ]
                    (List.map (\( value_, name ) -> option [ value value_, selected (model.filters.sort == value_) ] [ text name ]) LeaveFilters.sorts)
                ]
            , if model.refreshing && total /= Nothing then
                span [ class "lr-updating" ] [ span [ class "spinner-border spinner-border-sm", attribute "aria-hidden" "true" ] [], text "Updating" ]

              else
                text ""
            , if List.isEmpty picked then
                text ""

              else
                span [ class "lr-picked" ] [ text (String.fromInt (List.length picked) ++ " ticked · " ++ daysLabel pickedDays) ]
            ]
        , div [ class "lr-actions" ]
            (if List.isEmpty picked then
                case total of
                    Just n ->
                        if n > 0 then
                            [ button [ type_ "button", class "re-btn re-btn--primary", onClick (OpenReview Nothing) ]
                                [ text
                                    (if n > reviewLimit then
                                        "Review the first " ++ String.fromInt reviewLimit

                                     else if n == 1 then
                                        "Review it"

                                     else
                                        "Review these " ++ String.fromInt n
                                    )
                                , i [ class "bi bi-arrow-right", attribute "aria-hidden" "true" ] []
                                ]
                            ]

                        else
                            []

                    Nothing ->
                        []

             else
                [ button [ type_ "button", class "re-btn re-btn--primary", onClick ApproveSelected ]
                    [ i [ class "bi bi-check-lg", attribute "aria-hidden" "true" ] []
                    , text ("Approve " ++ plural (List.length picked) "request" "requests")
                    ]
                , button [ type_ "button", class "re-btn re-btn--quiet", onClick (SelectAll False) ] [ text "Untick all" ]
                ]
            )
        ]


{-| Requests approval mode draws at once, as the API does.
-}
reviewLimit : Int
reviewLimit =
    50


viewTable : Model -> T.LeaveOverviewOut -> Html Msg
viewTable model page =
    let
        looks =
            { registrars = Dict.fromList (List.map (\r -> ( r.id, r )) page.registrars), holidays = Dict.empty }

        ready =
            approvable model

        readyKeys =
            Set.fromList (List.map .key ready)

        allTicked =
            not (List.isEmpty ready) && List.all (\r -> Set.member r.key model.selected) ready
    in
    table [ class "lr-table" ]
        [ caption [ class "visually-hidden" ] [ text "Leave requests. Choose one to review it with its roster." ]
        , thead []
            [ tr []
                [ th [ scope "col", class "lr-col-tick" ]
                    (if List.isEmpty ready then
                        [ span [ class "visually-hidden" ] [ text "Tick to approve" ] ]

                     else
                        [ input
                            [ type_ "checkbox"
                            , checked allTicked
                            , onCheck SelectAll
                            , attribute "aria-label" ("Tick all " ++ String.fromInt (List.length ready) ++ " with nothing against them")
                            , title "Tick all with nothing against them"
                            ]
                            []
                        ]
                    )
                , th [ scope "col" ] [ text "Registrar" ]
                , th [ scope "col" ] [ text "Leave" ]
                , th [ scope "col", class "lr-col-num" ] [ text "Days" ]
                , th [ scope "col" ] [ text "Asked" ]
                , th [ scope "col" ] [ text "Chief registrar" ]
                , th [ scope "col" ] [ text "Director of Training" ]
                , th [ scope "col" ] [ text "Checks" ]
                ]
            ]
        , tbody []
            (List.concatMap
                (\row ->
                    viewRow model looks readyKeys row
                        :: (case model.shelf of
                                Just ( key, shelf ) ->
                                    if key == row.key then
                                        [ viewShelf model key shelf ]

                                    else
                                        []

                                Nothing ->
                                    []
                           )
                )
                page.rows
            )
        ]


viewRow : Model -> Lookups -> Set Int -> T.RequestRowOut -> Html Msg
viewRow model looks ready row =
    let
        registrar =
            Dict.get row.registrar looks.registrars

        name =
            Maybe.map .name registrar |> Maybe.withDefault "A registrar"

        typeName =
            leaveName (choiceFor model.flags.leaveTypes (T.leaveTypeToString row.type_))

        what =
            name ++ "'s " ++ String.toLower typeName ++ ", " ++ spanLabel [ row.start, row.end ]

        ticked =
            Set.member row.key model.selected

        cancelled =
            row.status == "cancelled"

        open =
            Maybe.map Tuple.first model.shelf == Just row.key
    in
    tr
        [ class "lr-row"
        , classList [ ( "is-ticked", ticked ), ( "is-cancelled", cancelled ), ( "is-open", open ) ]
        , on "click" (rowClickDecoder row.key)
        ]
        [ td [ class "lr-col-tick" ]
            [ if Set.member row.key ready then
                input
                    [ type_ "checkbox"
                    , checked ticked
                    , onCheck (Select row.key)
                    , attribute "aria-label" ("Tick " ++ what ++ " to approve")
                    ]
                    []

              else
                text ""
            ]
        , td [ class "lr-col-who" ]
            [ button
                [ type_ "button"
                , class "lr-rowlink"
                , id (rowId row.key)
                , stopPropagationOn "click" (Decode.succeed ( ToggleShelf row.key, True ))
                , attribute "aria-label" what
                , attribute "aria-expanded" (boolString open)
                , attribute "aria-controls" (shelfId row.key)
                ]
                [ i [ class "bi bi-chevron-right lr-chev", attribute "aria-hidden" "true" ] [], text name ]
            , if String.isEmpty row.comment then
                text ""

              else
                span [ class "lr-rownote", title row.comment ]
                    [ i [ class "bi bi-chat-left-quote", attribute "aria-hidden" "true" ] []
                    , span [ class "visually-hidden" ] [ text ("Their note: " ++ row.comment) ]
                    ]
            , case registrar |> Maybe.andThen (.year >> nullable) of
                Just year ->
                    span [ class "lr-rowyear" ] [ text ("Year " ++ String.fromInt year) ]

                Nothing ->
                    text ""
            ]
        , td [ class "lr-col-leave" ]
            [ strong [] [ text typeName ]
            , span [ class "lr-rowwhen" ]
                [ text
                    (spanLabel [ row.start, row.end ]
                        ++ (if row.portion == "ALL" then
                                ""

                            else
                                halfLabel row.portion
                           )
                    )
                ]
            ]
        , td [ class "lr-col-num" ]
            [ text (formatDays row.days)
            , -- The column's head names the unit, except on a phone.
              span [ class "lr-unit" ]
                [ text
                    (if row.days > 1 then
                        " days"

                     else
                        " day"
                    )
                ]
            ]
        , td [ class "lr-col-asked" ]
            (case nullable row.asked of
                Just at ->
                    [ text (Date.format "d MMM y" (Date.fromPosix model.zone at))
                    , span [ class "lr-rowsub" ] [ text (aheadOf (Date.fromPosix model.zone at) row.start) ]
                    ]

                Nothing ->
                    [ span [ class "lr-rowsub", title notRecorded ] [ text "Not recorded" ] ]
            )
        , -- Named on a phone, where the table's head is hidden.
          td [ class "lr-col-decision is-reg", attribute "data-label" "Chief registrar" ] [ viewRowDecision "reg" row ]
        , td [ class "lr-col-decision is-dot", attribute "data-label" "Director of Training" ] [ viewRowDecision "dot" row ]
        , td [ class "lr-col-checks" ] [ viewRowChecks model row ]
        ]


shelfId : Int -> String
shelfId key =
    "shelf-" ++ String.fromInt key


{-| A row opened in place: its request as approval mode draws it, roster and all, across the table.
-}
viewShelf : Model -> Int -> Remote T.LeaveRequestsOut -> Html Msg
viewShelf model key shelf =
    tr [ class "lr-shelf", id (shelfId key) ]
        [ td [ colspan 8 ]
            [ div [ class "lr-shelf-body" ]
                ((case shelf of
                    Loading ->
                        [ p [ class "lr-loading", attribute "role" "status" ]
                            [ span [ class "spinner-border spinner-border-sm", attribute "aria-hidden" "true" ] []
                            , text "Loading their roster"
                            ]
                        ]

                    Failed message ->
                        [ div [ class "re-note is-error lr-alert", attribute "role" "alert" ]
                            [ text message
                            , button [ type_ "button", class "re-btn", onClick (LoadShelf key) ] [ text "Try again" ]
                            ]
                        ]

                    Loaded data ->
                        List.map (viewRequest model (lookups data)) data.requests
                 )
                    ++ [ button
                            [ type_ "button"
                            , class "re-btn re-btn--quiet lr-shelf-close"
                            , onClick (ToggleShelf key)
                            , attribute "aria-controls" (shelfId key)
                            ]
                            [ i [ class "bi bi-chevron-up", attribute "aria-hidden" "true" ] [], text "Close" ]
                       ]
                )
            ]
        ]


{-| A click on a row opens its shelf, or closes it, unless it was on the tick or its cell. (Stopping the click there instead would
make Elm draw at once, and put the box back before its change arrives.)
-}
rowClickDecoder : Int -> Decoder Msg
rowClickDecoder key =
    Decode.map2
        (\type_ className ->
            if type_ == "checkbox" || String.contains "lr-col-tick" className then
                NoOp

            else
                ToggleShelf key
        )
        (Decode.oneOf [ Decode.at [ "target", "type" ] Decode.string, Decode.succeed "" ])
        (Decode.oneOf [ Decode.at [ "target", "className" ] Decode.string, Decode.succeed "" ])


{-| " (morning)", " (afternoon)", as `portionLabel` names a day's half.
-}
halfLabel : String -> String
halfLabel portion =
    case portion of
        "AM" ->
            " (morning)"

        "PM" ->
            " (afternoon)"

        _ ->
            ""


{-| One approver's decisions on a row's days, in a word or two.
-}
viewRowDecision : String -> T.RequestRowOut -> Html Msg
viewRowDecision approver row =
    let
        days =
            List.filter (not << .cancelled) row.leaves

        count f =
            List.length (List.filter f days)

        approved =
            count (\l -> decisionOf approver l == Just True)

        declined =
            count (\l -> decisionOf approver l == Just False)

        waiting =
            List.length (waitingIn approver days)

        mark cls icon label =
            span [ class ("lr-mark " ++ cls) ] [ i [ class ("bi " ++ icon), attribute "aria-hidden" "true" ] [], text label ]
    in
    if List.isEmpty days then
        span [ class "lr-mark is-cancelled" ] [ text "Cancelled" ]

    else if approved == List.length days then
        mark "is-approved" "bi-check-lg" "Approved"

    else if declined == List.length days then
        mark "is-declined" "bi-x-lg" "Declined"

    else if waiting == List.length days then
        mark "is-waiting" "bi-hourglass-split" "Waiting"

    else if waiting == 0 && approved == 0 && declined == 0 then
        -- Declined by the other approver before this one decided.
        span [ class "lr-mark" ] [ text "Not needed" ]

    else
        [ ( approved, "approved" ), ( declined, "declined" ), ( waiting, "waiting" ) ]
            |> List.filter (\( n, _ ) -> n > 0)
            |> List.map (\( n, what ) -> String.fromInt n ++ " " ++ what)
            |> String.join ", "
            |> (\label ->
                    mark
                        (if waiting > 0 then
                            "is-waiting"

                         else
                            ""
                        )
                        "bi-circle-half"
                        label
               )


{-| A waiting row's verdict in a few words; when the rest were decided.
-}
viewRowChecks : Model -> T.RequestRowOut -> Html Msg
viewRowChecks model row =
    case nullable row.checks of
        Just c ->
            let
                ( cls, icon, label ) =
                    case checksLevel c of
                        Bad ->
                            ( "is-bad"
                            , "bi-exclamation-triangle-fill"
                            , [ if c.breaks > 0 then
                                    Just (plural c.breaks "rule break" "rule breaks")

                                else
                                    Nothing
                              , if c.lost > 0 then
                                    Just "cover lost"

                                else
                                    Nothing
                              ]
                                |> List.filterMap identity
                                |> String.join ", "
                                |> capitalise
                            )

                        Concern ->
                            ( "is-concern"
                            , "bi-exclamation-circle-fill"
                            , if heatStep c.away c.roster == 4 then
                                "Busy: " ++ formatDays c.away ++ " of " ++ String.fromInt c.roster ++ " away"

                              else
                                String.fromInt (c.days - c.unrostered) ++ " of " ++ plural c.days "day" "days" ++ " rostered"
                            )

                        Unchecked ->
                            ( "is-unchecked", "bi-dash-circle", "Not rostered yet" )

                        Clear ->
                            ( "is-ok", "bi-check-circle-fill", "Nothing against it" )
            in
            span [ class ("lr-check " ++ cls) ] [ i [ class ("bi " ++ icon), attribute "aria-hidden" "true" ] [], text label ]

        Nothing ->
            case ( nullable row.decided, row.status ) of
                ( _, "cancelled" ) ->
                    text ""

                ( Just at, _ ) ->
                    span [ class "lr-rowsub" ] [ text ("Decided " ++ Date.format "d MMM y" (Date.fromPosix model.zone at)) ]

                ( Nothing, _ ) ->
                    text ""


viewOverviewEmpty : Model -> Html Msg
viewOverviewEmpty model =
    let
        default =
            LeaveFilters.isDefault (decides model.flags) model.filters
    in
    div [ class "lr-empty" ]
        (if default && model.filters.status == "mine" then
            [ i [ class "bi bi-check2-circle", attribute "aria-hidden" "true" ] []
            , p [] [ text "Nothing is waiting on you." ]
            , button [ type_ "button", class "re-btn re-btn--quiet", onClick (SetStatus "waiting") ] [ text "See everything waiting" ]
            ]

         else
            [ p [] [ text "No requests match these filters." ]
            , button [ type_ "button", class "re-btn re-btn--quiet", onClick ClearFilters ] [ text "Clear filters" ]
            ]
        )



-- APPROVAL MODE


viewReview : Model -> Html Msg
viewReview model =
    let
        sortName =
            LeaveFilters.sorts |> List.filter (Tuple.first >> (==) model.filters.sort) |> List.head |> Maybe.map Tuple.second |> Maybe.withDefault ""

        summary =
            case model.data of
                Loaded data ->
                    "Reviewing "
                        ++ (if data.total > List.length data.requests then
                                "the first " ++ String.fromInt (List.length data.requests) ++ " of " ++ thousands data.total

                            else
                                thousands data.total
                           )
                        ++ (if data.total == 1 then
                                " request · "

                            else
                                " requests · "
                           )
                        ++ LeaveFilters.statusLabel model.filters.status
                        ++ " · "
                        ++ sortName

                _ ->
                    "Reviewing · " ++ LeaveFilters.statusLabel model.filters.status
    in
    div [ class "lr-review" ]
        [ div [ class "lr-bar", id "lr-bar" ]
            [ div [ class "lr-review-head" ]
                [ button [ type_ "button", class "re-btn", onClick CloseReview ]
                    [ i [ class "bi bi-arrow-left", attribute "aria-hidden" "true" ] [], text "Overview" ]
                , p [ class "lr-review-title" ] [ text summary ]
                ]
            , -- The key to the "On leave" row, while one is drawn.
              if not (verdictFirst model.flags) || not (Set.isEmpty model.expanded) then
                viewScale

              else
                text ""
            ]
        , viewError model
        , case model.data of
            Loaded data ->
                if data.total > List.length data.requests then
                    p [ class "lr-limit" ] [ text ("These are the first " ++ String.fromInt (List.length data.requests) ++ ". Narrow the filters in the overview to review the rest.") ]

                else
                    text ""

            _ ->
                text ""
        , viewBody model
        ]


roleLine : Flags -> String
roleLine flags =
    case ( List.member "reg" flags.leaveApprovers, List.member "dot" flags.leaveApprovers ) of
        ( True, True ) ->
            "You decide as chief registrar, and can record the Director of Training's decisions for them."

        ( True, False ) ->
            "You decide as chief registrar."

        ( False, True ) ->
            "You decide as Director of Training. The chief registrar decides first; leave needs both approvals."

        ( False, False ) ->
            "You can see leave requests; the chief registrar and the Director of Training decide them."


viewHelp : Model -> Html Msg
viewHelp model =
    let
        -- Only the short forms that aren't simply the first word of the name.
        needsSaying c =
            Just (String.toLower c.short) /= List.head (String.words (String.toLower c.label))

        abbreviations =
            (model.flags.leaveTypes |> List.filter needsSaying |> List.map (\c -> c.short ++ " " ++ String.toLower (leaveName c)))
                ++ (model.flags.shiftTypes |> List.filter needsSaying |> List.map (\c -> c.short ++ " " ++ String.toLower c.label))
                ++ [ "RDO rostered day off" ]

        icon name label =
            span [ class "lr-help-icon" ] [ i [ class ("bi " ++ name), attribute "aria-hidden" "true" ] [], span [ class "visually-hidden" ] [ text label ] ]

        annual =
            (choiceFor model.flags.leaveTypes (T.leaveTypeToString T.LeaveType__ANNUAL)).short

        chip state =
            span [ class ("re-chip re-leave is-" ++ leaveStateClass state) ]
                [ i [ class ("bi " ++ leaveIcon state), attribute "aria-hidden" "true" ] [], text annual ]

        key k =
            kbd [] [ text k ]

        shortName shiftType =
            (choiceFor model.flags.shiftTypes (T.shiftTypeToString shiftType)).short
    in
    details [ class "lr-help" ]
        [ summary [] [ text "How this page works" ]
        , ul []
            [ li [] [ text "Leave needs two approvals, the chief registrar's and the Director of Training's; either can decline it." ]
            , li [] [ text "The overview lists the requests of registrars in training, filtered and sorted as you choose. Requests with nothing against them can be ticked and approved together; review the rest, with their roster, to decide them." ]
            , li []
                [ text "In review, approve or decline a whole request, or a single day with "
                , icon "bi-check-lg" "approve"
                , text " and "
                , icon "bi-x-lg" "decline"
                , text " in its column; pressing a day's decision again sets it back to waiting. The request's buttons only change the days still waiting for you. Every decision can be undone for a few seconds."
                ]
            , li [ class "lr-help-marks" ]
                [ text "Their roster: "
                , chip Pending
                , text " waiting on both, "
                , chip PartlyApproved
                , text " approved by one, "
                , chip Approved
                , text " approved. A day outlined in red, with its "
                , span [ class "re-clause" ] [ text "clause" ]
                , text ", is a rule break this leave would cause."
                ]
            , li [] [ text "On leave: everyone off that day, this request included, with a bar for their share of the roster. Click a day for their names." ]
            , li [ class "lr-help-marks" ]
                [ text "Cover lost: "
                , span [ class "lr-gap" ] [ i [ class "bi bi-exclamation-diamond-fill", attribute "aria-hidden" "true" ] [], text (shortName T.ShiftType__SWING) ]
                , text " cover this leave would lose, "
                , span [ class "lr-short" ] [ text (shortName T.ShiftType__NIGHT) ]
                , text " cover already short without it, and "
                , span [ class "lr-hatch", attribute "aria-hidden" "true" ] []
                , text " days not rostered yet, which can't be checked."
                ]
            , li [] [ text ("Short forms: " ++ String.join " · " abbreviations ++ ".") ]
            , li []
                [ text "Keys in review: "
                , key "j"
                , text " and "
                , key "k"
                , text " move between requests. With a request in focus, "
                , key "a"
                , text " approves and "
                , key "d"
                , text " declines what waits for you in it, and the arrow keys move around its roster. A request that would break a rule or lose cover takes you to its Approve button instead. "
                , key "Esc"
                , text " goes back to the overview."
                ]
            ]
        ]


{-| The colour scale of the "On leave" row, as a key.
-}
viewScale : Html Msg
viewScale =
    div [ class "lr-scale" ]
        [ span [ class "lr-scale-title" ] [ text "Share of the roster on leave" ]
        , ul [ class "lr-scale-steps" ]
            (List.map
                (\( step, label ) ->
                    li [] [ span [ class ("lr-swatch is-" ++ String.fromInt step), attribute "aria-hidden" "true" ] [], text label ]
                )
                [ ( 1, "under 10%" ), ( 2, "10–20%" ), ( 3, "20–30%" ), ( 4, "30% or more" ) ]
            )
        ]


viewToast : List Toast -> Html Msg
viewToast undos =
    case undos of
        t :: _ ->
            div [ class "re-toast" ]
                [ span [ class "re-toast-text" ] [ text t.message ]
                , button [ type_ "button", class "re-btn re-btn--on-dark", onClick Undo ]
                    [ i [ class "bi bi-arrow-counterclockwise", attribute "aria-hidden" "true" ] [], text "Undo" ]
                , button [ type_ "button", class "btn-close btn-close-white", attribute "aria-label" "Dismiss", onClick DismissToasts ] []
                ]

        [] ->
            text ""


viewBody : Model -> Html Msg
viewBody model =
    case model.data of
        Loading ->
            p [ class "lr-loading", attribute "role" "status" ]
                [ span [ class "spinner-border spinner-border-sm", attribute "aria-hidden" "true" ] []
                , text "Loading leave requests"
                ]

        Failed message ->
            div [ class "re-note is-error lr-alert", attribute "role" "alert" ]
                [ text message
                , text " "
                , button [ type_ "button", class "re-btn", onClick Reload ] [ text "Try again" ]
                ]

        Loaded data ->
            let
                groups =
                    groupsFor model data
            in
            if List.all (Tuple.second >> List.isEmpty) groups then
                viewEmpty model

            else
                div [ class "lr-list" ]
                    (List.filterMap
                        (\( heading, requests ) ->
                            if List.isEmpty requests then
                                Nothing

                            else
                                Just
                                    (section [ class "lr-group", attribute "aria-label" heading ]
                                        (h2 [ class "lr-group-title" ]
                                            [ text heading
                                            , span [ class "lr-group-count" ] [ text (String.fromInt (List.length requests)) ]
                                            ]
                                            :: List.map (viewRequest model (lookups data)) requests
                                        )
                                    )
                        )
                        groups
                    )


{-| The requests listed, in groups with a heading each: by month of their first day when in order of it, or
for the Director of Training reviewing what waits on them, those the chief registrar has approved first.
-}
groupsFor : Model -> T.LeaveRequestsOut -> List ( String, List T.LeaveRequestOut )
groupsFor model data =
    let
        byKey =
            Dict.fromList (List.map (\r -> ( requestKey r, r )) data.requests)

        requests =
            List.filterMap (\key -> Dict.get key byKey) model.shown

        firstDate r =
            List.head r.leaves |> Maybe.map .date
    in
    if verdictFirst model.flags && model.filters.status == "mine" && model.filters.sort == "leave" then
        let
            ( approved, unseen ) =
                List.partition (\r -> List.all (\l -> not (isActive l) || decisionOf "reg" l == Just True) r.leaves) requests
        in
        [ ( "Approved by the chief registrar", approved ), ( "Not yet decided by the chief registrar", unseen ) ]

    else if not (LeaveFilters.sortByLeave model.filters) then
        [ ( LeaveFilters.sorts |> List.filter (Tuple.first >> (==) model.filters.sort) |> List.head |> Maybe.map Tuple.second |> Maybe.withDefault "Requests", requests ) ]

    else
        requests
            |> List.foldr
                (\r acc ->
                    let
                        month =
                            firstDate r |> Maybe.map (Date.format "MMMM y") |> Maybe.withDefault ""
                    in
                    case acc of
                        ( m, rs ) :: rest ->
                            if m == month then
                                ( m, r :: rs ) :: rest

                            else
                                ( month, [ r ] ) :: acc

                        [] ->
                            [ ( month, [ r ] ) ]
                )
                []


viewEmpty : Model -> Html Msg
viewEmpty _ =
    div [ class "lr-empty" ]
        [ p [] [ text "No requests match these filters." ]
        , button [ type_ "button", class "re-btn re-btn--quiet", onClick CloseReview ] [ text "Back to the overview" ]
        ]


type alias Lookups =
    { registrars : Dict Int T.RegistrarOut
    , holidays : Dict Int String
    }


lookups : T.LeaveRequestsOut -> Lookups
lookups data =
    { registrars = Dict.fromList (List.map (\r -> ( r.id, r )) data.registrars)
    , holidays = Dict.fromList (List.map (\h -> ( Date.toRataDie h.date, h.name )) data.holidays)
    }


registrarName : Lookups -> Int -> String
registrarName looks id =
    Dict.get id looks.registrars |> Maybe.map .name |> Maybe.withDefault "A registrar"


viewRequest : Model -> Lookups -> T.LeaveRequestOut -> Html Msg
viewRequest model looks request =
    let
        key =
            requestKey request

        titleId =
            requestId key ++ "-title"

        registrar =
            Dict.get request.registrar looks.registrars

        first =
            List.head request.leaves

        days =
            List.map (\l -> weight l.portion) request.leaves |> List.sum

        comments =
            request.leaves |> List.map (.comment >> String.trim) |> List.filter (not << String.isEmpty) |> unique

        showRoster =
            showsRoster model key

        stripId =
            requestId key ++ "-roster"
    in
    article
        [ class "lr-request"
        , classList [ ( "has-roster", showRoster ) ]
        , id (requestId key)
        , tabindex -1
        , attribute "aria-labelledby" titleId
        , on "focusin" (Decode.succeed (EnterRequest key))

        -- Moving within the request, focusin follows at once and puts it back.
        , on "focusout" (Decode.succeed LeaveRequest)
        , on "keydown" (requestKeyDecoder key)
        ]
        [ div [ class "lr-side" ]
            [ h3 [ class "lr-name", id titleId ]
                [ text (Maybe.map .name registrar |> Maybe.withDefault "A registrar")
                , case registrar |> Maybe.andThen (.year >> nullable) of
                    Just year ->
                        span [ class "lr-year" ] [ text (" Year " ++ String.fromInt year) ]

                    Nothing ->
                        text ""
                ]
            , p [ class "lr-what" ]
                [ strong [] [ text (requestTypeName model request) ]
                , text
                    (" · "
                        ++ spanLabel (List.map .date request.leaves)
                        ++ (case first of
                                Just l ->
                                    if l.portion == "ALL" then
                                        ""

                                    else
                                        portionLabel l

                                Nothing ->
                                    ""
                           )
                        ++ " · "
                        ++ daysLabel days
                    )
                ]
            , p [ class "lr-meta" ] [ text (askedLine model.zone request) ]
            , viewHolidayNote looks request
            , if List.isEmpty comments then
                text ""

              else
                div [ class "lr-comment" ]
                    [ i [ class "bi bi-chat-left-quote", attribute "aria-hidden" "true" ] []
                    , div [] (List.map (\c -> p [] [ text c ]) comments)
                    ]
            , viewVerdict model looks request
            , viewDecide model looks request
            , case Dict.get key model.failed of
                Just ( message, _ ) ->
                    div [ class "re-note is-error lr-alert", attribute "role" "alert" ]
                        [ text message
                        , button [ type_ "button", class "re-btn", onClick (Retry key) ] [ text "Try again" ]
                        ]

                Nothing ->
                    text ""
            , div [ class "lr-links" ]
                ((if verdictFirst model.flags then
                    [ button
                        [ type_ "button"
                        , class "re-btn re-btn--quiet"
                        , attribute "aria-expanded" (boolString showRoster)
                        , attribute "aria-controls" stripId
                        , onClick (ToggleRoster key)
                        ]
                        [ i
                            [ class
                                (if showRoster then
                                    "bi bi-chevron-up"

                                 else
                                    "bi bi-chevron-down"
                                )
                            , attribute "aria-hidden" "true"
                            ]
                            []
                        , text
                            (if showRoster then
                                "Hide their roster"

                             else
                                "Show their roster"
                            )
                        ]
                    ]

                  else
                    []
                 )
                    ++ [ a [ class "re-btn re-btn--quiet", href (editorLink model request) ]
                            [ i [ class "bi bi-calendar-week", attribute "aria-hidden" "true" ] [], text "Open in the roster editor" ]
                       ]
                )
            ]
        , if showRoster then
            div [ class "lr-main", id stripId ]
                [ div
                    [ class "lr-strip"
                    , classList [ ( "is-faded", List.length request.dates > 9 && not (Set.member key model.scrolledEnd) ) ]
                    , on "scroll" (scrolledDecoder key)
                    ]
                    [ viewGrid model looks request ]
                , viewDayNames model looks request
                ]

          else
            text ""

        -- After the roster: what to weigh it against, the rule breaks and the leave they've had.
        , div [ class "lr-context" ] [ viewBreaks request, viewYears model request ]
        ]


{-| Leave asked for on a public holiday, which is a day off already: "Includes Mon 8 Feb, Waitangi Day
(observed), a public holiday."
-}
viewHolidayNote : Lookups -> T.LeaveRequestOut -> Html Msg
viewHolidayNote looks request =
    let
        holidays =
            activeDays request
                |> List.filterMap (\d -> Dict.get d looks.holidays |> Maybe.map (\name -> Date.format "EEE d MMM" (Date.fromRataDie d) ++ ", " ++ name))
    in
    case holidays of
        [] ->
            text ""

        [ one ] ->
            p [ class "lr-note" ]
                [ i [ class "bi bi-calendar-event", attribute "aria-hidden" "true" ] []
                , text ("Includes " ++ one ++ ", a public holiday.")
                ]

        many ->
            p [ class "lr-note" ]
                [ i [ class "bi bi-calendar-event", attribute "aria-hidden" "true" ] []
                , text ("Includes public holidays: " ++ String.join "; " many ++ ".")
                ]


scrolledDecoder : Int -> Decoder Msg
scrolledDecoder key =
    Decode.map3 (\left width client -> StripScrolled key (left + client >= width - 4))
        (Decode.at [ "target", "scrollLeft" ] Decode.float)
        (Decode.at [ "target", "scrollWidth" ] Decode.float)
        (Decode.at [ "target", "clientWidth" ] Decode.float)


editorLink : Model -> T.LeaveRequestOut -> String
editorLink model request =
    case List.head request.leaves of
        Just leave ->
            model.flags.editorUrl ++ Date.toIsoString leave.date ++ "/"

        Nothing ->
            model.flags.editorUrl


{-| "Asked 3 Aug 2026, 178 days ahead"
-}
askedLine : Time.Zone -> T.LeaveRequestOut -> String
askedLine zone request =
    case ( nullable request.asked, List.head request.leaves ) of
        ( Just at, Just first ) ->
            let
                asked =
                    Date.fromPosix zone at
            in
            "Asked " ++ Date.format "d MMM y" asked ++ ", " ++ aheadOf asked first.date

        _ ->
            "When it was asked for wasn't recorded: " ++ String.toLower notRecorded


{-| "178 days ahead", "on the day", "3 days after it began"
-}
aheadOf : Date -> Date -> String
aheadOf asked start =
    let
        ahead =
            Date.diff Date.Days asked start
    in
    if ahead > 0 then
        plural ahead "day" "days" ++ " ahead"

    else if ahead == 0 then
        "on the day"

    else
        plural (negate ahead) "day" "days" ++ " after it began"


notRecorded : String
notRecorded =
    "It was loaded from the old system."


{-| How a request's verdict reads, from its checks:

  - Bad (red): the leave loses cover or breaks a rule.
  - Concern (ochre): a busy day (30% or more of the roster away), or some of its days not rostered yet.
  - Unchecked (grey): none of its days rostered yet, so nothing to check against.
  - Clear (green): every day checked, and nothing found.

-}
type Level
    = Bad
    | Concern
    | Unchecked
    | Clear


checksLevel : T.RequestChecksOut -> Level
checksLevel c =
    if c.breaks > 0 || c.lost > 0 then
        Bad

    else if heatStep c.away c.roster == 4 then
        Concern

    else if c.days > 0 && c.unrostered == c.days then
        Unchecked

    else if c.unrostered > 0 then
        Concern

    else
        Clear


{-| The answer to "can it be given?" in one line: how many would be away, the cover it loses, and the rule
breaks it causes. It is only as sure as the roster: days not rostered yet can't be checked, and it says so.
-}
viewVerdict : Model -> Lookups -> T.LeaveRequestOut -> Html Msg
viewVerdict model _ request =
    let
        asked =
            activeDays request

        unrostered =
            List.filter (\d -> not (dayInfo request d |> Maybe.map .rostered |> Maybe.withDefault False)) asked

        peak =
            asked
                |> List.map (\d -> ( awayOn request d, dayInfo request d |> Maybe.map .registrars |> Maybe.withDefault 0 ))
                |> List.sortBy (\( n, of_ ) -> negate (n / toFloat (Basics.max 1 of_)))
                |> List.head

        busy =
            case peak of
                Just ( n, of_ ) ->
                    heatStep n of_ == 4

                Nothing ->
                    False

        lost =
            lostCover model request

        noneRostered =
            not (List.isEmpty asked) && List.length unrostered == List.length asked

        ( level, icon ) =
            case
                checksLevel
                    { breaks = List.length request.violations
                    , lost = List.length lost
                    , days = List.length asked
                    , unrostered = List.length unrostered
                    , away = Maybe.map Tuple.first peak |> Maybe.withDefault 0
                    , roster = Maybe.map Tuple.second peak |> Maybe.withDefault 0
                    }
            of
                Bad ->
                    ( "is-bad", "bi-exclamation-triangle-fill" )

                Concern ->
                    ( "is-concern", "bi-exclamation-circle-fill" )

                Unchecked ->
                    ( "is-unchecked", "bi-dash-circle" )

                Clear ->
                    ( "is-ok", "bi-check-circle-fill" )

        away =
            case peak of
                Just ( n, of_ ) ->
                    (if List.length asked > 1 then
                        "Up to "

                     else
                        ""
                    )
                        ++ formatDays n
                        ++ " of "
                        ++ String.fromInt of_
                        ++ " on leave"
                        ++ (if busy then
                                " (" ++ String.fromInt (round (100 * n / toFloat (Basics.max 1 of_))) ++ "%)"

                            else
                                ""
                           )

                Nothing ->
                    "Nothing left to give"

        cover =
            if noneRostered then
                "not rostered yet"

            else
                case lost of
                    [] ->
                        "no cover lost"

                    [ one ] ->
                        one ++ " lost"

                    _ ->
                        "cover lost on " ++ plural (List.length lost) "shift" "shifts"

        breaks =
            case ( List.length request.violations, noneRostered ) of
                ( 0, True ) ->
                    "cover and rule breaks unchecked"

                ( 0, False ) ->
                    "no rule breaks caused"

                ( n, _ ) ->
                    plural n "rule break" "rule breaks" ++ " caused"

        partly =
            if noneRostered || List.isEmpty unrostered then
                []

            else
                [ String.fromInt (List.length unrostered) ++ " of " ++ plural (List.length asked) "day" "days" ++ " not rostered yet" ]

        parts =
            [ away, cover, breaks ] ++ partly

        clauses =
            request.violations |> List.map (\v -> nullable v.clause |> Maybe.withDefault "Department rule") |> unique
    in
    p [ class ("lr-verdict " ++ level) ]
        [ i [ class ("bi " ++ icon), attribute "aria-hidden" "true" ] []
        , span []
            -- Each part ends with its separator, so a line never starts with one.
            (parts
                |> List.indexedMap
                    (\index part ->
                        span [ class "lr-verdict-part" ]
                            (text
                                (if index < List.length parts - 1 then
                                    part ++ " ·"

                                 else
                                    part
                                )
                                :: (if part == breaks && not (List.isEmpty clauses) then
                                        List.map (\c -> span [ class "re-clause" ] [ text c ]) clauses

                                    else
                                        []
                                   )
                            )
                    )
                |> List.intersperse (text " ")
            )
        ]


{-| The request's own buttons, for the user's first decision: they only change the days still waiting for
them. Once none are, a summary of what they decided.
-}
viewDecide : Model -> Lookups -> T.LeaveRequestOut -> Html Msg
viewDecide model looks request =
    let
        key =
            requestKey request

        active =
            List.filter (\l -> not l.cancelled) request.leaves

        busy =
            List.any (\l -> Set.member l.id model.saving) request.leaves

        status =
            case unique (List.map leaveStateSentence active) of
                [ one ] ->
                    one

                [] ->
                    "Cancelled."

                _ ->
                    mixedStatus active

        whose =
            registrarName looks request.registrar ++ "'s " ++ String.toLower (requestTypeName model request)

        risk =
            riskOf model request
    in
    div [ class "lr-decide" ]
        ((case primaryApprover model.flags of
            Just approver ->
                let
                    waiting =
                        waitingFor approver request

                    -- Some days already decided, declined ones included: say which days the buttons change.
                    some =
                        List.length waiting < List.length active

                    days =
                        if some then
                            Just (plural (List.length waiting) "waiting day" "waiting days")

                        else
                            Nothing

                    -- "Approve", "Approve 3 waiting days despite 1 rule break"
                    label verb despite =
                        verb
                            ++ (days |> Maybe.map ((++) " ") |> Maybe.withDefault "")
                            ++ (despite |> Maybe.map ((++) " despite ") |> Maybe.withDefault "")

                    -- "Approve Erika Lee's annual leave", "Approve the 1 waiting day of Erika Lee's annual leave"
                    spoken verb despite =
                        verb
                            ++ (days |> Maybe.map (\d -> " the " ++ d ++ " of ") |> Maybe.withDefault " ")
                            ++ whose
                            ++ (despite |> Maybe.map ((++) " despite ") |> Maybe.withDefault "")

                    action decision verb icon variant attrs =
                        let
                            despite =
                                if decision then
                                    risk

                                else
                                    Nothing
                        in
                        button
                            ([ type_ "button"
                             , class ("re-btn " ++ variant)
                             , disabled busy
                             , attribute "aria-label" (spoken verb despite)
                             , onClick (Decide True { key = key, approver = approver, leaves = waiting, decision = Just decision })
                             ]
                                ++ attrs
                            )
                            [ i [ class ("bi " ++ icon), attribute "aria-hidden" "true" ] []
                            , text (label verb despite)
                            ]

                    -- Changing a decided request: every day it can still have, one way or the other.
                    other =
                        if approver == "reg" then
                            "dot"

                        else
                            "reg"

                    changeable =
                        List.filter (\l -> decisionOf other l /= Just False) active

                    allTo decision verb icon attrs =
                        let
                            leaves =
                                List.filter (\l -> decisionOf approver l /= Just decision) changeable
                        in
                        if List.isEmpty leaves then
                            Nothing

                        else
                            Just
                                (button
                                    ([ type_ "button"
                                     , class "re-btn"
                                     , disabled busy
                                     , attribute "aria-label" (verb ++ " all of " ++ whose)
                                     , onClick (Decide False { key = key, approver = approver, leaves = leaves, decision = Just decision })
                                     ]
                                        ++ attrs
                                    )
                                    [ i [ class ("bi " ++ icon), attribute "aria-hidden" "true" ] [], text (verb ++ " all") ]
                                )
                in
                if Set.member key model.settled && not (Set.member key model.changing) then
                    [ p [ class "lr-mine" ] [ text (mineSummary approver request) ]
                    , button [ type_ "button", class "re-btn", id (requestId key ++ "-start-change"), onClick (StartChange key) ]
                        [ i [ class "bi bi-pencil", attribute "aria-hidden" "true" ] [], text "Change decision" ]
                    ]

                else if Set.member key model.settled then
                    let
                        -- The first control takes focus when the change starts.
                        first =
                            [ id (requestId key ++ "-change") ]

                        approveAll =
                            allTo True "Approve" "bi-check-lg" first

                        declineAll =
                            allTo False
                                "Decline"
                                "bi-x-lg"
                                (if approveAll == Nothing then
                                    first

                                 else
                                    []
                                )
                    in
                    [ p [ class "lr-mine" ]
                        [ text
                            (mineSummary approver request
                                ++ (if showsRoster model key then
                                        " Change a day in its column, or all at once."

                                    else
                                        ""
                                   )
                            )
                        ]
                    , div [ class "lr-actions" ]
                        (List.filterMap identity [ approveAll, declineAll ]
                            ++ [ button
                                    ([ type_ "button", class "re-btn re-btn--quiet", onClick (EndChange key) ]
                                        ++ (if approveAll == Nothing && declineAll == Nothing then
                                                first

                                            else
                                                []
                                           )
                                    )
                                    [ text "Done" ]
                               ]
                        )
                    ]

                else if List.isEmpty waiting then
                    [ p [ class "lr-mine" ]
                        [ text
                            (mineSummary approver request
                                ++ (if showsRoster model key then
                                        " Change a day in its column."

                                    else
                                        ""
                                   )
                            )
                        ]
                    ]

                else
                    [ div [ class "lr-actions" ]
                        [ -- Approving despite a cost isn't the obvious action, so it loses the primary fill.
                          action True
                            "Approve"
                            "bi-check-lg"
                            (if risk == Nothing then
                                "re-btn--primary"

                             else
                                ""
                            )
                            [ id (requestId key ++ "-approve") ]
                        , action False "Decline" "bi-x-lg" "re-btn--danger-quiet" []
                        ]
                    ]

            Nothing ->
                []
         )
            ++ [ p [ class "lr-status", attribute "aria-live" "polite" ] [ text status ] ]
        )


{-| Whether a request's roster is drawn: always, except for the Director of Training until they ask.
-}
showsRoster : Model -> Int -> Bool
showsRoster model key =
    not (verdictFirst model.flags) || Set.member key model.expanded


{-| "You approved all 5 days.", "You approved 4 days and declined 1."
-}
mineSummary : String -> T.LeaveRequestOut -> String
mineSummary approver request =
    let
        count value =
            List.length (List.filter (\l -> not l.cancelled && decisionOf approver l == Just value) request.leaves)

        approved =
            count True

        declined =
            count False

        total =
            List.length (List.filter (not << .cancelled) request.leaves)
    in
    if approved == total && total > 1 then
        "You approved all " ++ String.fromInt total ++ " days."

    else if approved == total then
        "You approved it."

    else if declined == total && total > 1 then
        "You declined all " ++ String.fromInt total ++ " days."

    else if declined == total then
        "You declined it."

    else if declined == 0 && approved > 0 then
        "You approved " ++ plural approved "day" "days" ++ "; the rest were declined by the other approver."

    else if approved == 0 && declined > 0 then
        "You declined " ++ plural declined "day" "days" ++ "; the rest were declined by the other approver."

    else
        "You approved " ++ plural approved "day" "days" ++ " and declined " ++ String.fromInt declined ++ "."


{-| "2 days approved, 1 declined, 14 waiting", for a request decided differently from day to day.
-}
mixedStatus : List T.LeaveOut -> String
mixedStatus leaves =
    let
        count state =
            List.length (List.filter (\l -> leaveState l == state) leaves)

        waiting =
            count Pending + count PartlyApproved
    in
    [ ( count Approved, "approved" ), ( count Declined, "declined" ), ( waiting, "waiting" ) ]
        |> List.filter (\( n, _ ) -> n > 0)
        |> List.indexedMap
            (\index ( n, what ) ->
                if index == 0 then
                    plural n "day" "days" ++ " " ++ what

                else
                    String.fromInt n ++ " " ++ what
            )
        |> String.join ", "


{-| The rule breaks this leave would cause, and, folded away, those already on their roster.
-}
viewBreaks : T.LeaveRequestOut -> Html Msg
viewBreaks request =
    let
        rule v =
            li []
                [ span [ class "re-clause" ] [ text (nullable v.clause |> Maybe.withDefault "Department rule") ]
                , text v.message
                ]
    in
    if List.isEmpty request.violations && List.isEmpty request.existing_violations then
        text ""

    else
        div [ class "lr-breaks" ]
            [ if List.isEmpty request.violations then
                text ""

              else
                div []
                    [ h4 [ class "re-label" ] [ text ("Caused by this leave: " ++ plural (List.length request.violations) "rule break" "rule breaks") ]
                    , ul [ class "re-rulelist" ] (List.map rule request.violations)
                    ]
            , if List.isEmpty request.existing_violations then
                text ""

              else
                details [ class "lr-existing" ]
                    [ summary [ class "re-label" ] [ text (plural (List.length request.existing_violations) "rule break" "rule breaks" ++ " already on their roster") ]
                    , ul [ class "re-rulelist" ] (List.map rule request.existing_violations)
                    ]
            ]


{-| The registrar's leave by year and type, to weigh the request against what they've had: the year it
falls in (or both, across the start of one) in full, and earlier years behind a disclosure.
-}
viewYears : Model -> T.LeaveRequestOut -> Html Msg
viewYears model request =
    let
        ( lead, earlier ) =
            List.partition .lead request.years
    in
    if List.isEmpty request.years then
        text ""

    else
        section [ class "lr-years", attribute "aria-label" "Their leave by year" ]
            (List.map (viewLeadYear model) lead
                ++ [ if List.isEmpty earlier then
                        text ""

                     else
                        viewEarlierYears model earlier
                   ]
            )


viewLeadYear : Model -> T.LeaveYearOut -> Html Msg
viewLeadYear model year =
    let
        headingId =
            "lr-year-" ++ Date.toIsoString year.start ++ "-" ++ String.fromInt (Date.toRataDie year.end)

        cell kind n =
            if n == 0 then
                td [ class "is-none" ] [ text "–" ]

            else
                td [ class kind ] [ text (formatDays n) ]

        row tally =
            tr [ classList [ ( "is-asked", tally.request > 0 ) ] ]
                [ th [ scope "row" ] [ text (leaveTypeLabel model tally.type_) ]
                , cell "" tally.approved
                , cell "is-waiting" tally.waiting
                , if tally.request == 0 then
                    td [ class "is-none" ] [ text "–" ]

                  else
                    td [ class "is-request" ] [ text ("+" ++ formatDays tally.request) ]
                , td [ class "is-total" ] [ text (formatDays (tally.approved + tally.waiting + tally.request)) ]
                ]
    in
    div [ class "lr-year-block" ]
        [ h4 [ class "re-label", id headingId ]
            [ text ("Leave in " ++ leaveYearName year)
            , span [ class "lr-year-span" ] [ text (Date.format "d MMM y" year.start ++ " – " ++ Date.format "d MMM y" year.end) ]
            ]
        , if List.isEmpty year.types then
            p [ class "lr-status" ] [ text "None this year." ]

          else
            table [ class "lr-tally", attribute "aria-labelledby" headingId ]
                [ thead []
                    [ tr []
                        [ th [ scope "col" ] [ span [ class "visually-hidden" ] [ text "Type" ] ]
                        , th [ scope "col" ] [ text "Approved" ]
                        , th [ scope "col" ] [ text "Waiting" ]
                        , th [ scope "col" ] [ text "This request" ]
                        , th [ scope "col", title "Approved, waiting and this request together" ] [ text "Total" ]
                        ]
                    ]
                , tbody [] (List.map row year.types)
                ]
        ]


{-| Earlier years, types down the side as in the year above, the days in each year that weren't declined.
-}
viewEarlierYears : Model -> List T.LeaveYearOut -> Html Msg
viewEarlierYears model years =
    let
        types =
            model.flags.leaveTypes
                |> List.map .value
                |> List.filter (\t -> List.any (.types >> List.any (\y -> T.leaveTypeToString y.type_ == t)) years)

        days t year =
            year.types
                |> List.filter (\y -> T.leaveTypeToString y.type_ == t)
                |> List.map (\y -> y.approved + y.waiting + y.request)
                |> List.sum
    in
    details [ class "lr-earlier" ]
        [ summary [ class "re-label" ] [ text "Earlier years" ]
        , div [ class "lr-tally-scroll" ]
            [ table [ class "lr-tally" ]
                [ thead []
                    [ tr []
                        (th [ scope "col" ] [ span [ class "visually-hidden" ] [ text "Type" ] ]
                            :: List.map (\y -> th [ scope "col", title (Date.format "d MMM y" y.start ++ " – " ++ Date.format "d MMM y" y.end) ] [ text (leaveYearName y) ]) years
                        )
                    ]
                , tbody []
                    (types
                        |> List.map
                            (\t ->
                                tr []
                                    (th [ scope "row" ] [ text (choiceFor model.flags.leaveTypes t).label ]
                                        :: List.map
                                            (\y ->
                                                if days t y == 0 then
                                                    td [ class "is-none" ] [ text "–" ]

                                                else
                                                    td [] [ text (formatDays (days t y)) ]
                                            )
                                            years
                                    )
                            )
                    )
                ]
            ]
        ]


{-| "2026–27": a leave year runs from February to the next January.
-}
leaveYearName : T.LeaveYearOut -> String
leaveYearName year =
    String.fromInt (Date.year year.start) ++ "–" ++ String.right 2 (String.fromInt (Date.year year.end))


leaveTypeLabel : Model -> T.LeaveType -> String
leaveTypeLabel model leaveType =
    (choiceFor model.flags.leaveTypes (T.leaveTypeToString leaveType)).label


viewGrid : Model -> Lookups -> T.LeaveRequestOut -> Html Msg
viewGrid model looks request =
    let
        key =
            requestKey request

        asked =
            Dict.fromList (List.map (\l -> ( Date.toRataDie l.date, l )) request.leaves)

        columnClasses date =
            [ ( "is-weekend", isWeekend date )
            , ( "is-holiday", Dict.member (Date.toRataDie date) looks.holidays )
            , ( "is-asked", Dict.member (Date.toRataDie date) asked )
            ]

        dated =
            List.indexedMap Tuple.pair request.dates

        row label cells =
            markedRow label (\_ -> []) cells

        -- A row whose cells carry their own marks too.
        markedRow label marks cells =
            tr [] (th [ scope "row", class "lr-rowlabel" ] label :: List.map (\( i, date ) -> td [ classList (columnClasses date ++ marks date) ] (cells i date)) dated)

        -- The rule breaks this leave would cause, by the days they touch.
        breaks =
            request.violations
                |> List.concatMap (\v -> List.map (\date -> ( Date.toRataDie date, v )) v.dates)
                |> List.foldl (\( d, v ) acc -> Dict.update d (\vs -> Just (Maybe.withDefault [] vs ++ [ v ])) acc) Dict.empty

        breaksOn date =
            Dict.get (Date.toRataDie date) breaks |> Maybe.withDefault []

        decisionRow index approver who =
            let
                canChange =
                    List.member approver model.flags.leaveApprovers && editable model key

                waiting =
                    waitingFor approver request
            in
            row
                [ span [ class "lr-rowname" ] [ text who ]
                , if canChange && List.length waiting > 1 then
                    span [ class "lr-rowall" ]
                        [ button
                            [ type_ "button"
                            , class "lr-mini"
                            , attribute "aria-label" ("Approve every waiting day as " ++ who)
                            , title ("Approve every waiting day as " ++ who)
                            , onClick (Decide False { key = key, approver = approver, leaves = waiting, decision = Just True })
                            ]
                            [ i [ class "bi bi-check-lg", attribute "aria-hidden" "true" ] [], text "all" ]
                        , button
                            [ type_ "button"
                            , class "lr-mini"
                            , attribute "aria-label" ("Decline every waiting day as " ++ who)
                            , title ("Decline every waiting day as " ++ who)
                            , onClick (Decide False { key = key, approver = approver, leaves = waiting, decision = Just False })
                            ]
                            [ i [ class "bi bi-x-lg", attribute "aria-hidden" "true" ] [], text "all" ]
                        ]

                  else
                    text ""
                ]
                (\i date ->
                    case Dict.get (Date.toRataDie date) asked of
                        Just leave ->
                            [ viewDecision model request index i approver who canChange leave ]

                        Nothing ->
                            []
                )

        rosters =
            request.days |> List.map .registrars |> unique

        ofRoster =
            case ( List.minimum rosters, List.maximum rosters ) of
                ( Just lo, Just hi ) ->
                    if lo == hi then
                        "of " ++ String.fromInt lo

                    else
                        "of " ++ String.fromInt lo ++ "–" ++ String.fromInt hi

                _ ->
                    ""
    in
    table [ class "lr-grid", attribute "aria-label" ("Roster around " ++ registrarName looks request.registrar ++ "'s leave") ]
        [ thead []
            [ tr []
                (th [ class "lr-corner" ] [ span [ class "visually-hidden" ] [ text "Day" ] ]
                    :: List.map
                        (\date ->
                            let
                                holiday =
                                    Dict.get (Date.toRataDie date) looks.holidays
                            in
                            th [ scope "col", classList (columnClasses date) ]
                                [ span [ class "lr-weekday" ] [ text (Date.format "EEE" date) ]
                                , span [ class "lr-daydate" ] [ text (Date.format "d MMM" date) ]
                                , case holiday of
                                    Just name ->
                                        span [ class "lr-holiday" ] [ text name ]

                                    Nothing ->
                                        text ""
                                ]
                        )
                        request.dates
                )
            ]
        , tbody []
            [ markedRow [ text "Their roster" ]
                (\date -> [ ( "has-break", not (List.isEmpty (breaksOn date)) ) ])
                (\_ date -> viewOwnDay model request asked date ++ viewBreakTags (breaksOn date))
            , decisionRow 0 "reg" "Chief registrar"
            , decisionRow 1 "dot" "Director of Training"
            , row [ span [ class "lr-rowname" ] [ text "On leave" ], span [ class "lr-rowsub" ] [ text (ofRoster ++ " on the roster") ] ]
                (\i date -> [ viewAway model request key i date ])
            , viewCoverRow model looks request
            ]
        ]


{-| The clauses of the rule breaks this leave would cause on a day, each naming the break.
-}
viewBreakTags : List T.ViolationOut -> List (Html Msg)
viewBreakTags violations =
    if List.isEmpty violations then
        []

    else
        [ div [ class "lr-breaktags" ]
            (List.map
                (\v ->
                    span [ class "re-clause", title v.message ]
                        [ span [ class "visually-hidden" ] [ text "Rule break: " ]
                        , text (nullable v.clause |> Maybe.withDefault "Department rule")
                        , span [ class "visually-hidden" ] [ text (", " ++ v.message) ]
                        ]
                )
                violations
            )
        ]


{-| The cover the leave would lose, day by day. Days not rostered yet run together into one hatched cell,
since there is nothing in them to check.
-}
viewCoverRow : Model -> Lookups -> T.LeaveRequestOut -> Html Msg
viewCoverRow model looks request =
    let
        rostered date =
            dayInfo request (Date.toRataDie date) |> Maybe.map .rostered |> Maybe.withDefault False

        asked =
            List.map (.date >> Date.toRataDie) request.leaves

        -- Runs of days, each rostered day on its own.
        runs =
            List.foldr
                (\date acc ->
                    case acc of
                        ((next :: _) as run) :: rest ->
                            if not (rostered date) && not (rostered next) then
                                (date :: run) :: rest

                            else
                                [ date ] :: acc

                        _ ->
                            [ date ] :: acc
                )
                []
                request.dates

        cell run =
            case run of
                [ date ] ->
                    if rostered date then
                        td
                            [ classList
                                [ ( "is-weekend", isWeekend date )
                                , ( "is-holiday", Dict.member (Date.toRataDie date) looks.holidays )
                                , ( "is-asked", List.member (Date.toRataDie date) asked )
                                ]
                            ]
                            [ viewCover model (dayInfo request (Date.toRataDie date)) ]

                    else
                        td [ class "is-unrostered" ] [ span [ class "lr-unrostered" ] [ text "Not rostered" ] ]

                _ ->
                    td [ class "is-unrostered lr-unrostered-run", colspan (List.length run) ]
                        [ span [ class "lr-unrostered" ] [ text "Not rostered yet" ] ]
    in
    tr [] (th [ scope "row", class "lr-rowlabel" ] [ text "Cover lost" ] :: List.map cell runs)


viewOwnDay : Model -> T.LeaveRequestOut -> Dict Int T.LeaveOut -> Date -> List (Html Msg)
viewOwnDay model request asked date =
    let
        d =
            Date.toRataDie date

        shifts =
            List.filter (\s -> Date.toRataDie s.date == d) request.shifts

        leaves =
            (Dict.get d asked |> Maybe.map List.singleton |> Maybe.withDefault [])
                ++ List.filter (\l -> Date.toRataDie l.date == d) request.other_leave

        leaveChip leave =
            let
                choice =
                    choiceFor model.flags.leaveTypes (T.leaveTypeToString leave.type_)

                state =
                    leaveState leave
            in
            span [ class (leaveChipClass state leave), title (leaveName choice ++ portionLabel leave ++ ", " ++ leaveStateName state) ]
                (leaveChipContent choice state leave ++ [ span [ class "visually-hidden" ] [ text (", " ++ leaveStateName state) ] ])

        shiftChip shift =
            let
                choice =
                    choiceFor model.flags.shiftTypes (T.shiftTypeToString shift.type_)
            in
            span [ class ("re-chip re-shift is-" ++ String.toLower (T.shiftTypeToString shift.type_)), title choice.label ]
                [ span [ attribute "aria-hidden" "true" ] [ text choice.short ], span [ class "visually-hidden" ] [ text choice.label ] ]
    in
    if List.isEmpty shifts && List.isEmpty leaves then
        []

    else
        [ div [ class "lr-chips" ] (List.map shiftChip shifts ++ List.map leaveChip leaves) ]


{-| One approver's decision on one day: approve and decline toggles for someone who can make it, the
decision in words for someone who can't, with who made it.
-}
viewDecision : Model -> T.LeaveRequestOut -> Int -> Int -> String -> String -> Bool -> T.LeaveOut -> Html Msg
viewDecision model request row index approver who canChange leave =
    let
        current =
            decisionOf approver leave

        by =
            decidedLine model.zone approver leave

        saving =
            Set.member leave.id model.saving

        toggleButton offset value icon verb variant =
            let
                on_ =
                    current == value
            in
            button
                ([ type_ "button"
                 , class ("lr-toggle " ++ variant)
                 , classList [ ( "is-on", on_ ) ]
                 , attribute "aria-pressed" (boolString on_)
                 , attribute "aria-label" (verb ++ " " ++ Date.format "EEE d MMM" leave.date ++ " as " ++ who)
                 , title
                    (if on_ then
                        by ++ ". Press again to set it back to waiting."

                     else
                        verb
                    )
                 , disabled saving
                 , onClick
                    (Decide False
                        { key = requestKey request
                        , approver = approver
                        , leaves = [ leave ]
                        , decision =
                            if on_ then
                                Nothing

                            else
                                value
                        }
                    )
                 ]
                    ++ spotAttributes model request ( row, index * 2 + offset )
                )
                [ i [ class ("bi " ++ icon), attribute "aria-hidden" "true" ] [] ]
    in
    if canChange && not leave.cancelled then
        div []
            [ div [ class "lr-decision", classList [ ( "is-saving", saving ) ] ]
                [ toggleButton 0 (Just True) "bi-check-lg" "Approve" "is-approve"
                , toggleButton 1 (Just False) "bi-x-lg" "Decline" "is-decline"
                ]
            , if current == Nothing || saving then
                text ""

              else
                viewBy model.zone approver leave
            ]

    else
        case current of
            Just True ->
                span [ class "lr-state is-approved" ]
                    [ i [ class "bi bi-check-lg", attribute "aria-hidden" "true" ] []
                    , text "Approved"
                    , viewBy model.zone approver leave
                    ]

            Just False ->
                span [ class "lr-state is-declined" ]
                    [ i [ class "bi bi-x-lg", attribute "aria-hidden" "true" ] []
                    , text "Declined"
                    , viewBy model.zone approver leave
                    ]

            Nothing ->
                span [ class "lr-state" ] [ text "Waiting" ]


{-| "Approved by Az, 7 Oct 2026, 16:21"
-}
decidedLine : Time.Zone -> String -> T.LeaveOut -> String
decidedLine zone approver leave =
    let
        ( by, at ) =
            if approver == "reg" then
                ( nullable leave.reg_decided_by, nullable leave.reg_decided_at )

            else
                ( nullable leave.dot_decided_by, nullable leave.dot_decided_at )

        verb =
            case decisionOf approver leave of
                Just True ->
                    "Approved"

                Just False ->
                    "Declined"

                Nothing ->
                    "Waiting"
    in
    verb
        ++ (by |> Maybe.map (\name -> " by " ++ name) |> Maybe.withDefault "")
        ++ (at |> Maybe.map (\time -> ", " ++ dateTime zone time) |> Maybe.withDefault "")


{-| Who decided and when, in a few words under the decision: "Az · 7 Oct".
-}
viewBy : Time.Zone -> String -> T.LeaveOut -> Html Msg
viewBy zone approver leave =
    let
        ( by, at ) =
            if approver == "reg" then
                ( nullable leave.reg_decided_by, nullable leave.reg_decided_at )

            else
                ( nullable leave.dot_decided_by, nullable leave.dot_decided_at )

        parts =
            List.filterMap identity [ by, Maybe.map (Date.fromPosix zone >> Date.format "d MMM") at ]
    in
    if List.isEmpty parts then
        text ""

    else
        span [ class "lr-by", title (decidedLine zone approver leave) ] [ text (String.join " · " parts) ]


{-| Everyone on leave that day, this request included, shaded by their share of the roster. Opens the names.
-}
viewAway : Model -> T.LeaveRequestOut -> Int -> Int -> Date -> Html Msg
viewAway model request key index date =
    let
        d =
            Date.toRataDie date

        others =
            List.filter (\a -> Date.toRataDie a.date == d) request.away

        mine =
            List.filter (\l -> Date.toRataDie l.date == d && isActive l) request.leaves

        count =
            awayOn request d

        waiting =
            List.length (List.filter (not << .approved) others) + List.length (List.filter (\l -> leaveState l /= Approved) mine)

        rostered =
            dayInfo request d |> Maybe.map .registrars |> Maybe.withDefault 0

        open =
            model.openDay == Just ( key, d )

        label =
            formatDays count
                ++ " on leave"
                ++ (if rostered > 0 then
                        " of " ++ String.fromInt rostered ++ " on the roster"

                    else
                        ""
                   )
                ++ (if waiting > 0 then
                        ", " ++ String.fromInt waiting ++ " still waiting"

                    else
                        ""
                   )
                ++ " on "
                ++ Date.format "EEE d MMM" date
    in
    button
        ([ type_ "button"
         , class ("lr-heat is-" ++ String.fromInt (heatStep count rostered))
         , classList [ ( "is-open", open ) ]
         , attribute "aria-expanded" (boolString open)
         , attribute "aria-controls" (requestId key ++ "-names")
         , attribute "aria-label" (label ++ ". Show who.")
         , title label
         , onClick (ToggleDay key d)
         ]
            ++ spotAttributes model request ( 2, index * 2 )
        )
        [ text (formatDays count)
        , span [ class "lr-heat-bar", attribute "aria-hidden" "true" ] []
        ]


viewDayNames : Model -> Lookups -> T.LeaveRequestOut -> Html Msg
viewDayNames model looks request =
    let
        key =
            requestKey request

        content =
            case model.openDay of
                Just ( k, d ) ->
                    if k /= key then
                        []

                    else
                        let
                            leaveLabel type_ portion =
                                (choiceFor model.flags.leaveTypes (T.leaveTypeToString type_)).short
                                    ++ (if portion == "ALL" then
                                            ""

                                        else
                                            " " ++ String.toLower portion
                                       )

                            mine =
                                List.filter (\l -> Date.toRataDie l.date == d && isActive l) request.leaves

                            others =
                                List.filter (\a -> Date.toRataDie a.date == d) request.away

                            group heading names =
                                if List.isEmpty names then
                                    Nothing

                                else
                                    Just
                                        (div [ class "lr-daygroup" ]
                                            [ dt [] [ text heading ]
                                            , dd [] [ text (String.join ", " names) ]
                                            ]
                                        )

                            name a =
                                registrarName looks a.registrar ++ " (" ++ leaveLabel a.type_ a.portion ++ ")"
                        in
                        [ strong [ class "lr-dayname" ] [ text (Date.format "EEE d MMM" (Date.fromRataDie d)) ]
                        , if List.isEmpty mine && List.isEmpty others then
                            p [] [ text "Nobody on leave." ]

                          else
                            dl []
                                (List.filterMap identity
                                    [ group "This request" (List.map (\_ -> registrarName looks request.registrar) mine)
                                    , group "Approved" (others |> List.filter .approved |> List.map name)
                                    , group "Waiting" (others |> List.filter (not << .approved) |> List.map name)
                                    ]
                                )
                        ]

                Nothing ->
                    []
    in
    div
        [ class "lr-daynames"
        , classList [ ( "is-empty", List.isEmpty content ) ]
        , id (requestId key ++ "-names")
        , attribute "aria-live" "polite"
        ]
        content


{-| The cover the leave would lose that day, and, quieter, the cover already short whatever happens.
-}
viewCover : Model -> Maybe T.RequestDayOut -> Html Msg
viewCover model info =
    case info of
        Just day ->
            if List.isEmpty day.lost && List.isEmpty day.short then
                span [ class "visually-hidden" ] [ text "Nothing lost" ]

            else
                let
                    names need =
                        List.map (\t -> (choiceFor model.flags.shiftTypes (T.shiftTypeToString t)).short) need |> String.join "/"

                    full need =
                        List.map (shiftName model) need |> String.join " or "
                in
                div [ class "lr-chips" ]
                    (List.map
                        (\need ->
                            span [ class "lr-gap", title (full need ++ ": nobody else is rostered, so the leave loses it") ]
                                [ i [ class "bi bi-exclamation-diamond-fill", attribute "aria-hidden" "true" ] []
                                , text (names need)
                                , span [ class "visually-hidden" ] [ text " lost" ]
                                ]
                        )
                        day.lost
                        ++ List.map
                            (\need ->
                                span [ class "lr-short", title (full need ++ ": already short before this leave") ]
                                    [ text (names need)
                                    , span [ class "visually-hidden" ] [ text " already short" ]
                                    ]
                            )
                            day.short
                    )

        Nothing ->
            text ""



-- HELPERS


nullable : Nullable a -> Maybe a
nullable value =
    case value of
        Present a ->
            Just a

        Null ->
            Nothing


unique : List comparable -> List comparable
unique items =
    List.foldl
        (\item ( seen, acc ) ->
            if Set.member item seen then
                ( seen, acc )

            else
                ( Set.insert item seen, acc ++ [ item ] )
        )
        ( Set.empty, [] )
        items
        |> Tuple.second


indexOf : a -> List a -> Maybe Int
indexOf item items =
    items
        |> List.indexedMap Tuple.pair
        |> List.filter (\( _, x ) -> x == item)
        |> List.head
        |> Maybe.map Tuple.first


boolString : Bool -> String
boolString b =
    if b then
        "true"

    else
        "false"


plural : Int -> String -> String -> String
plural n one many =
    String.fromInt n
        ++ " "
        ++ (if n == 1 then
                one

            else
                many
           )


isWeekend : Date -> Bool
isWeekend date =
    Date.weekdayNumber date >= 6


{-| "Mon 12 – Fri 16 Oct 2026", "Mon 28 Sep – Fri 2 Oct 2026", "Fri 16 Oct 2026"
-}
spanLabel : List Date -> String
spanLabel dates =
    case ( List.head dates, List.head (List.reverse dates) ) of
        ( Just first, Just last ) ->
            if first == last then
                Date.format "EEE d MMM y" first

            else if Date.year first /= Date.year last then
                Date.format "EEE d MMM y" first ++ " – " ++ Date.format "EEE d MMM y" last

            else if Date.month first /= Date.month last then
                Date.format "EEE d MMM" first ++ " – " ++ Date.format "EEE d MMM y" last

            else
                Date.format "EEE d" first ++ " – " ++ Date.format "EEE d MMM y" last

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
